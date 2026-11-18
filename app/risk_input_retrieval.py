"""Public-API-first risk evidence, bounded REST-only AI fallback and automation."""
from __future__ import annotations

from copy import deepcopy
import asyncio
from datetime import datetime, timezone
from threading import RLock, Thread
import time
from uuid import uuid4
from zoneinfo import ZoneInfoNotFoundError
import httpx

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .auth import SESSION_COOKIE_NAME
from .risk_input_sources import PublicRiskAPIs, extract_risk_records, extract_proposed_risk_records, no_registration_fields
from .country_currency_reference import CountryCurrencyReference, SIX_CURRENCY_URL
from .security_enrichment import EnrichmentJobs, WEB_RESEARCH_POLICY, MAX_SELECTED
from .security_research_tools import ResearchSession, ResearchFailure, WebRequestBudget
from .security_search import SearchFailure, search_is_configured
from .scheduling import normalize_schedule, schedule_trigger
from .research_diagnostics import event as diagnostic_event, failure as safe_failure, receipt, snapshot

PREFIX = "/api/securities/risk-inputs/retrieval"
CHILD_PREFIX = "/api/securities/risk-inputs/research"
SCHEDULE_ENDPOINT = "/api/settings/risk-input-retrieval-schedule"
JOB_ID = "risk-input-retrieval"
MODES = {"api_then_ai", "api", "ai"}
REFRESH_POLICIES = {"missing", "stale", "refresh_existing"}
POLICY = WEB_RESEARCH_POLICY + (
    " This task is RISK INPUT evidence, not prices. For refresh_requested=true, re-read current primary sources for requested_fields even when no field is missing. Read exact primary issuer filings, "
    "government offering documents or the verified issuer website. Select only risk_input/credit_rating context_records "
    "returned by the application. An address is issuer domicile only; it is never economic allocation. "
    "A trading/reporting currency never proves economic currency exposure. Do not manufacture ratings, "
    "duration, current spread/yield, geographic percentages or fund diversification. Unknowns remain unknown. "
    "Return records:[{security_key,source_id,record_id}] using actual returned IDs. "
    "For additional explicitly reported facts, return risk_claims:[{security_key,source_id,field,value,as_of,units,evidence_quote}]. "
    "When the local planner schema uses value_json, encode that value as JSON text there; the application decodes it before validation. "
    "Copy the exact complete dated source sentence or table including its headings into evidence_quote; the server parses and validates it. "
    "Supported fields include currency_exposures/country_exposures (maps with fraction or percent units), country_code, country_currency, "
    "instrument_kind, maturity_date, plain_nominal_noncallable, zero_coupon_confirmed, sovereign_currency_basis, "
    "current_spread_bps (basis points), continuous_yield (annual continuously compounded decimal or percent), "
    "cashflows (dated complete future payments) and fund_holdings ([{identifier,weight}]). "
    "A multi-country allocation does not establish a single-country model input. A coupon or ordinary yield-to-maturity is not a continuous discount yield. "
    "For country_currency, use the official ISO4217 reference hint and read its exact country name with query. "
    "It supplies a country's currency-shock axis, never a company's economic FX weights or economic country allocation. "
    "For long reports, use query or offset on read_security_source to inspect later sections; do not treat the opening window as the entire report. "
)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _user(request, write=False):
    actor = getattr(request.state, "auth_user", None)
    if not isinstance(actor, dict):
        raise HTTPException(401, "authentication_required")
    if write and actor.get("role") not in {"Admin", "Operator"}:
        raise HTTPException(403, "read_only")
    return actor


def missing_fields(risk, candidate, _depth=0):
    fields = []
    params = risk.get("parameters") or {}
    asset = str(candidate.get("asset_class") or candidate.get("asset_sub_class") or "").upper()
    kind = params.get("instrument_kind") or ({"EQUITY":"equity", "STOCK":"equity", "RSU":"equity", "ETF":"fund", "MUTUALFUND":"fund", "FUND":"fund"}.get(asset))
    if risk.get("unsupported_bond") is True or risk.get("requires_recovery_model") is True:
        fields.append("unsupported_instrument")
    if risk.get("error") or risk.get("status") == "unavailable":
        fields.append("parameters_unavailable")
    if (asset in {"EQUITY", "STOCK", "RSU"} and kind != "equity"
            or asset in {"ETF", "MUTUALFUND", "FUND"} and kind != "fund"
            or asset in {"BOND", "FIXED_INCOME"} and kind not in {None, "corporate_bond", "sovereign_bond"}):
        fields.append("asset_class")
    if kind == "fund":
        # The model prices the constituents, not the fund manager. Requiring
        # wrapper issuer/country facts cannot complete or validate lookthrough.
        children = risk.get("lookthrough") or []
        if (_depth >= 3 or risk.get("lookthrough_verified") is not True or not children
                or risk.get("lookthrough_missing")):
            return list(dict.fromkeys(fields + ["fund_lookthrough"]))
        try:
            import math
            weights = [child["weight"] for child in children]
            if any(type(weight) not in {int,float} or not math.isfinite(weight) or not 0 <= weight <= 1 for weight in weights) or not math.isclose(sum(weights),1,abs_tol=1e-8):
                return list(dict.fromkeys(fields + ["fund_lookthrough"]))
        except (KeyError, TypeError):
            return list(dict.fromkeys(fields + ["fund_lookthrough"]))
        required = []
        for child in children:
            item = child.get("item") or {}
            if child["weight"] > 0:
                required.extend(missing_fields(item.get("stress_risk") or {}, item.get("holding") or {}, _depth+1))
        return list(dict.fromkeys(fields + (["fund_lookthrough"] if required else []) + required))
    if kind not in {"equity", "corporate_bond", "sovereign_bond"} and asset not in {"BOND", "FIXED_INCOME"}:
        fields.append("unsupported_instrument")
    if not risk.get("issuer_id"):
        fields.append("issuer_identity")
    if not (risk.get("country") or {}).get("country_code"):
        fields.append("country")
    elif (risk.get("country") or {}).get("basis") != "economic_exposure":
        fields.append("country_exposure")
    if not risk.get("country_rating"):
        fields.append("country_rating")
    if not params.get("country_currency"):
        fields.append("country_currency")
    if not risk.get("currency_exposures") and kind not in {"corporate_bond", "sovereign_bond"}:
        fields.append("fx")
    if asset in {"BOND", "FIXED_INCOME"} or kind in {"corporate_bond", "sovereign_bond"}:
        if kind not in {"corporate_bond", "sovereign_bond"}:
            fields.append("bond_kind")
        if not (risk.get("sovereign_rating") if kind == "sovereign_bond" else risk.get("credit_rating")):
            fields.append("credit_rating")
        for field, present in (("bond_maturity",params.get("maturity_date")),("bond_terms",params.get("plain_nominal_noncallable")),
            ("current_spread",params.get("current_spread_bps") is not None),
            ("bond_cashflows",params.get("pricing_model") == "zero_coupon_continuous" and params.get("zero_coupon_confirmed") or params.get("cashflows"))):
            if not present:
                fields.append(field)
        if kind == "sovereign_bond" and not params.get("sovereign_currency_basis"):
            fields.append("sovereign_currency_basis")
        if kind == "corporate_bond" and params.get("country_sensitivity") is None:
            fields.append("country_sensitivity")
        if params.get("pricing_model") == "cashflows_continuous" and params.get("continuous_yield") is None:
            fields.append("bond_yield")
        try:
            observed=datetime.fromisoformat(params.get("as_of") or "").date()
            if not 0 <= (datetime.now(timezone.utc).date()-observed).days <= 7:
                fields.append("parameters_stale")
        except ValueError:
            fields.append("parameters_stale")
    if risk.get("parameters_verification") == "user_entered" and params.get("assumptions_enabled") is not True:
        fields.append("parameters_unverified")
    return list(dict.fromkeys(fields))


def refresh_fields(risk, candidate):
    """Request instrument evidence again; each fetched claim still needs validation."""
    fields = ["issuer_identity", "issuer_domicile", "country_exposure", "country_rating", "country_currency"]
    kind = (risk.get("parameters") or {}).get("instrument_kind")
    if candidate.get("asset_class") == "BOND" or kind in {"corporate_bond", "sovereign_bond"}:
        fields += ["bond_kind", "credit_rating", "bond_maturity", "bond_terms", "bond_cashflows", "current_spread", "bond_yield"]
        fields += ["sovereign_currency_basis"] if kind == "sovereign_bond" else ["country_sensitivity"]
    else:
        fields.append("fx")
    if kind == "fund" or candidate.get("asset_class") in {"FUND", "ETF", "MUTUALFUND"}:
        fields.append("fund_lookthrough")
    return list(dict.fromkeys(missing_fields(risk, candidate) + fields))


class RetrievalStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    security_keys: list[str] | None = Field(default=None,min_length=1,max_length=MAX_SELECTED)
    mode: str = "api_then_ai"
    language: str | None = None
    position_scope: str = "open"
    refresh_policy: str = "missing"


class RiskEvidenceResearch:
    """Application callbacks validate fetched sources; the planner sees REST only."""
    def __init__(self, inputs, research_settings, *, api_sources=None, changed=None, credit_service=None, sovereign_service=None, reference_reader=None):
        self.inputs, self.research_settings = inputs, research_settings
        self.api_sources = api_sources or PublicRiskAPIs()
        self.changed = changed or (lambda:None)
        self.credit_service, self.sovereign_service = credit_service, sovereign_service
        self.reference_reader = reference_reader or CountryCurrencyReference()
        self._sessions, self._outcomes, self._lock = {}, {}, RLock()

    def candidates(self, position_scope="open", security_keys=None, refresh_policy="missing"):
        if position_scope not in {"open", "all"} or refresh_policy not in REFRESH_POLICIES:
            raise HTTPException(422,"invalid_retrieval_request")
        selected = set(security_keys or [])
        rows = []
        for candidate in self.inputs.inventory():
            if (str(candidate.get("stock_market") or "").upper() == "PRIVATE"
                    or str(candidate.get("asset_class") or "").upper() in {"CASH","CURRENCY","PRIVATE_STOCK","EMPLOYEE_STOCK_OPTION","STOCK_OPTION"}):
                continue
            if position_scope == "open" and not candidate.get("has_open_position"):
                continue
            if selected and candidate["security_key"] not in selected:
                continue
            risk = self.inputs.read(candidate)
            needed = missing_fields(risk,candidate)
            eligible = [field for field in needed if not field.endswith("_stale")] if refresh_policy == "missing" else needed
            if not eligible and refresh_policy != "refresh_existing":
                continue
            evidence = self.inputs.evidence(candidate).get("fields") or {}
            rows.append({**candidate,"missing_fields":needed,
                "requested_fields":refresh_fields(risk,candidate) if refresh_policy == "refresh_existing" else needed,
                "refresh_requested":refresh_policy == "refresh_existing","identity_token":self.inputs.identity(candidate),
                "expected_revision":risk["revision"],"researched_issuer_name":evidence.get("issuer_name",{}).get("value"),
                "researched_issuer_id":evidence.get("issuer_id",{}).get("value"),
                "api_supported_fields":no_registration_fields(candidate),
                "ai_supported_fields":["issuer_identity","issuer_domicile","country_exposure","country_currency","fx",
                    "country_rating","credit_rating","bond_kind","bond_maturity","bond_terms","bond_cashflows",
                    "bond_yield","current_spread","sovereign_currency_basis","country_sensitivity","fund_lookthrough"],
                "country_code":(risk.get("country") or {}).get("country_code"),
                "captured_at":_now(),
                "source_evidence":risk.get("source_evidence",[])})
        settings=self.research_settings()
        return {"items":rows,"total_count":len(rows),"truncated":False,
                "research_available":search_is_configured(settings) or any(row.get("website") or row.get("source_evidence") for row in rows),
                "configured_search_providers":["yahoo","duckduckgo"]+(["brave"] if settings.get("search_api_key") else [])}

    def public_api(self, candidate):
        latest = self.inputs.candidate(candidate["security_key"])
        if self.inputs.identity(latest) != candidate["identity_token"]:
            raise HTTPException(409,"risk_input_identity_changed")
        result = self.api_sources.fetch(latest)
        if result["records"]:
            self.inputs.publish_evidence(latest,result["records"],expected_revision=candidate["expected_revision"])
            self.changed()
        return result

    def _session(self,candidate):
        key = candidate.get("_request_id") or ""
        with self._lock:
            if key not in self._sessions:
                settings=self.research_settings()
                limits=getattr(self,"_manager",None)
                limit=limits._job(key)["counts"]["max_web_requests"] if limits and key else min(8,max(1,int(settings.get("max_web_calls",8))))
                self._sessions[key] = ResearchSession(settings,WebRequestBudget(limit=limit,timeout_seconds=90),fetch=self.reference_reader.fetch_document)
                for old in list(self._sessions)[:-100]:
                    self._sessions.pop(old,None)
            return self._sessions[key]

    def research_tool(self,candidate,action,arguments):
        latest = self.inputs.candidate(candidate["security_key"])
        if self.inputs.identity(latest) != candidate.get("identity_token"):
            return {"evidence":[],"source_status":"identity_changed"}
        session = self._session(candidate)
        try:
            if action == "discover":
                leads = [(row.get("source_url"),"Previously verified primary risk input source") for row in candidate.get("source_evidence",[])]
                for row in candidate.get("source_evidence",[]):
                    if row.get("field") == "filing_sources":
                        leads = [(filing["url"],"Exact SEC filing with bound reporting date") for filing in row.get("value",[])] + leads
                leads += [(candidate.get(field),"Issuer source; discovery only") for field in ("website","issuer_website")]
                from .credit_rating_service import ISSUER_SOURCES, AGENCY_SOURCE_LEADS
                from .credit_ratings import _matches_entity
                leads += [(url,"Official company rating source; discovery only") for entity,url in (*ISSUER_SOURCES,*AGENCY_SOURCE_LEADS) if _matches_entity(entity,candidate)]
                from .sovereign_ratings import SOURCE_LEADS
                leads += [(url,"Official sovereign rating source; discovery only") for url in SOURCE_LEADS.get(candidate.get("country_code"),[])]
                if candidate.get("country_code") and "country_currency" in candidate.get("requested_fields",candidate.get("missing_fields",[])):
                    from .sovereign_ratings import country_descriptor
                    country = country_descriptor(candidate["country_code"])
                    if country:
                        leads.insert(0,(SIX_CURRENCY_URL,"Official ISO4217 country currency reference; read with query="+country["country_name"]))
                sources=[]
                seen=set()
                for url,title in leads:
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    try:
                        identifier=session._add(candidate["security_key"],url,title)
                    except ResearchFailure:
                        continue
                    sources.append({"source_id":identifier,"url":url,"title":title,"discovery_only":True})
                return {"sources":sources[:3],"evidence":[],"source_status":"sources_found","web_requests":session.budget.used}
            if action == "search":
                result=session.search(candidate,arguments.get("query",""),provider=arguments.get("provider","auto"))
                return {**result,"evidence":[],"source_status":"search_results","web_requests":session.budget.used}
            options = {key:arguments[key] for key in ("reader","query","offset") if arguments.get(key) is not None}
            source = (session.read(candidate,arguments["source_id"],**options) if action == "read"
                else session.follow(candidate,arguments["source_id"],arguments["link_id"],**options))
            validation=self._validation_source(source,candidate)
            records=[record for record in extract_risk_records(validation,candidate)
                if self._quote_visible(record,source)]
            source["context_records"]=[{**r,"kind":"risk_input","security_key":candidate["security_key"]} for r in records]
            source["context_records"].extend({**record,"kind":"credit_rating","security_key":candidate["security_key"]}
                for _,record,_,_ in self._rating_records(validation,candidate) if self._quote_visible(record,source))
            return {"evidence":[source],"source_status":"evidence_found","web_requests":session.budget.used,"diagnostics":dict(session.diagnostics)}
        except (ResearchFailure,SearchFailure,ValueError,OSError,TimeoutError) as exc:
            return {"evidence":[],"source_status":getattr(exc,"code","source_read_failed"),"web_requests":session.budget.used,"diagnostics":dict(session.diagnostics)}

    @staticmethod
    def _quote_visible(record, source):
        quote=" ".join(str(record.get("evidence_quote") or "").split())
        return bool(quote and quote in " ".join(str(source.get("text") or "").split()))

    def _validation_source(self,source,candidate,request_id=None):
        if not source.get("document_id"):
            return self._dated_source(source,candidate)
        identifier=request_id or candidate.get("_request_id") or ""
        session=self._sessions.get(identifier)
        if session is None:
            raise ResearchFailure("invalid_source","The source snapshot is no longer available for validation.")
        return self._dated_source(session.validation_source(candidate,source["source_id"],source["document_id"]),candidate)

    def _rating_records(self,source,candidate):
        output=[]
        if self.credit_service:
            from .credit_ratings import extract_rating_records, normalize_observation
            subject=self.credit_service.candidate(candidate["security_key"])
            if subject:
                for record in extract_rating_records(source,subject):
                    try:
                        output.append(("security",record,normalize_observation(record,subject,source=source),subject))
                    except ValueError:
                        pass
        if self.sovereign_service and candidate.get("country_code"):
            from .sovereign_ratings import extract_rating_records, normalize_observation
            subject=self.sovereign_service.candidate(candidate["country_code"])
            if subject:
                for record in extract_rating_records(source,subject):
                    try:
                        output.append(("country",record,normalize_observation(record,subject,source=source),subject))
                    except ValueError:
                        pass
        return output

    @staticmethod
    def _dated_source(source,candidate):
        # Only the exact accession/document captured from submissions can lend
        # its reportDate to that filing. Generic page/footer dates cannot.
        for evidence in candidate.get("source_evidence",[]):
            if evidence.get("field") == "filing_sources":
                for filing in evidence.get("value",[]):
                    if source.get("url") == filing.get("url"):
                        return {**source,"observation_date":filing["as_of"],"published_at":filing["published_at"]}
        return source

    def finalize(self,outcomes,user_id,request_id,*,proposal=None,evidence_by_key=None,candidates=None,**_):
        from .security_web_research import parse_research_proposal
        parsed=parse_research_proposal(proposal) or {}
        choices={(r.get("security_key"),r.get("source_id"),r.get("record_id")) for r in parsed.get("records",[]) if isinstance(r,dict)}
        claims=parsed.get("risk_claims",[])
        claims=claims[:100] if isinstance(claims,list) else []
        finalized=[]
        for key,candidate in (candidates or {}).items():
            accepted=[]
            ratings={"security":[],"country":[]}
            rating_subjects={}
            latest=self.inputs.candidate(key)
            if self.inputs.identity(latest) != candidate.get("identity_token") or self.inputs.read(latest)["revision"] != candidate.get("expected_revision"):
                finalized.append({**candidate,"status":"not_attempted","code":"identity_changed","attempted":False,"available_fields":[],"missing_fields":candidate.get("missing_fields",[])})
                continue
            validated_documents={}
            for source in (evidence_by_key or {}).get(key,[]):
                # Windows of one retained immutable document have identical
                # full-source validation. Parse once, then retain the separate
                # window visibility and selected-record checks below.
                document_key=(source.get("source_id"),source.get("document_id")) if source.get("document_id") else None
                cached=validated_documents.get(document_key) if document_key else None
                if cached is None:
                    validation=self._validation_source(source,candidate,request_id)
                    cached=(validation,extract_risk_records(validation,candidate),self._rating_records(validation,candidate),{})
                    if document_key:
                        validated_documents[document_key]=cached
                validation,source_records,source_ratings,source_claims=cached
                accepted.extend(r for r in source_records if self._quote_visible(r,source)
                    and (key,source.get("source_id"),r["record_id"]) in choices)
                for claim_index,claim in enumerate(claims):
                    if isinstance(claim,dict) and claim.get("security_key")==key and claim.get("source_id")==source.get("source_id"):
                        quote=" ".join(str(claim.get("evidence_quote") or "").split())
                        if quote and quote in " ".join(str(source.get("text") or "").split()):
                            if claim_index not in source_claims:
                                source_claims[claim_index]=extract_proposed_risk_records(validation,candidate,claim)
                            accepted.extend(source_claims[claim_index])
                for category,record,normalized,subject in source_ratings:
                    if self._quote_visible(record,source) and (key,source.get("source_id"),record["record_id"]) in choices:
                        ratings[category].append(normalized)
                        rating_subjects[category]=subject
            code="data_unavailable"
            current_country=(self.inputs.read(latest).get("country") or {}).get("country_code")
            accepted=[record for record in accepted if record.get("basis") != "iso4217_country_reference"
                or record.get("country_code") == current_country]
            if accepted:
                try:
                    self.inputs.publish_evidence(candidate,accepted,expected_revision=candidate["expected_revision"])
                    self.changed()
                    code="data_found"
                except HTTPException:
                    code="identity_changed"
                    accepted=[]
            rating_fields=[]
            for category,service,field in (("security",self.credit_service,"credit_ratings"),("country",self.sovereign_service,"country_rating")):
                if ratings[category] and service.publish(rating_subjects[category],ratings[category],started_at=candidate.get("captured_at")):
                    rating_fields.append(field)
                    self.changed()
                    code="data_found"
            current=self.inputs.read(self.inputs.candidate(key))
            row={**candidate,"status":"partial" if accepted or rating_fields else "unavailable","code":code,
                "available_fields":sorted({r["field"] for r in accepted}|set(rating_fields)),"missing_fields":missing_fields(current,candidate),
                "sources":[{"url":r["source_url"],"source_kind":r["source_kind"],"retrieved_at":r["retrieved_at"],"as_of":r.get("as_of"),
                    "basis":r.get("basis"),"reference_published_at":r.get("reference_published_at"),
                    "reference_cache_status":r.get("reference_cache_status"),"fields":[r["field"]]} for r in accepted],
                "attempted":bool((evidence_by_key or {}).get(key)),"retrieval_mode":"public_ai"}
            finalized.append(row)
            self._outcomes[key]=deepcopy(row)
        return finalized

    def manager(self,app,settings,*,event_writer=None):
        manager=EnrichmentJobs(app,settings,candidate_reader=self.candidates,
            security_fetcher=lambda *_:{"evidence":[],"source_status":"data_unavailable"},
            outcome_reader=lambda:deepcopy(list(self._outcomes.values())),outcome_writer=self.finalize,
            research_tool_fetcher=self.research_tool,source_hint_reader=lambda c:self.research_tool(c,"discover",{}).get("sources",[]),
            prefix=CHILD_PREFIX,research_policy=POLICY,selection_reader=True,
            # Full fetched evidence stays in the application-owned candidate
            # for validation. Repeating every field's quotation in the initial
            # model prompt can exceed its existing8k limit after an API update.
            research_metadata={"identity_token","expected_revision","issuer_name","researched_issuer_name","researched_issuer_id","verified_issuer_domains","country_code","captured_at"},
            discovery_subject="official annual report investment country economic currency exposure risk inputs",refresh_portfolio_on_update=False,
            event_writer=event_writer,persist_research_trace=False)
        self._manager=manager
        return manager


class RiskInputRetrieval:
    def __init__(self, evidence, ai_jobs, credit_jobs, country_jobs, *, event_writer=None,worker_factory=Thread,poll_seconds=.25):
        self.evidence,self.ai_jobs,self.credit_jobs,self.country_jobs=evidence,ai_jobs,credit_jobs,country_jobs
        self.worker_factory,self.poll_seconds=worker_factory,poll_seconds
        self.app = getattr(ai_jobs,"app",None)
        self._lock,self._jobs,self._cursors=RLock(),{},{}
        self._event_writer=event_writer

    def _event(self,job,name,**fields):
        diagnostic_event(job,self._event_writer,name,**fields)

    def diagnostics(self,identifier,owner):
        with self._lock:
            self.get(identifier,owner)
            job=self._jobs[identifier]
            return receipt(job,job.get("children",[]))

    @staticmethod
    def _public(job):
        return deepcopy({k:v for k,v in job.items() if not k.startswith("_")})

    def get(self,identifier,owner):
        with self._lock:
            job=self._jobs.get(identifier)
            if not job or job["_owner"] != owner:
                raise HTTPException(404,"retrieval_job_not_found")
            return self._public(job)

    def status(self,owner):
        with self._lock:
            jobs=[j for j in self._jobs.values() if j["_owner"] == owner]
            active=next((j for j in reversed(jobs) if j["status"] in {"queued","running"}),None)
            return {"active_job":self._public(active) if active else None,"last_job":self._public(jobs[-1]) if jobs else None}

    def start(self,owner,headers,language="en",*,security_keys=None,mode="api_then_ai",scheduled_credentials=None,batch_offset=None,
              position_scope="open",refresh_policy="missing",parent_request_id=None):
        if mode not in MODES or language not in {"en","he"} or position_scope not in {"open","all"} or refresh_policy not in REFRESH_POLICIES:
            raise HTTPException(422,"invalid_retrieval_request")
        if security_keys is not None and (not isinstance(security_keys,list) or not 1<=len(security_keys)<=MAX_SELECTED or any(not isinstance(k,str) or not 1<=len(k)<=300 for k in security_keys)):
            raise HTTPException(422,"invalid_retrieval_request")
        keys=list(dict.fromkeys(k.strip().upper() for k in security_keys)) if security_keys else None
        with self._lock:
            active=next((j for j in self._jobs.values() if j["status"] in {"queued","running"}),None)
            if active:
                if (scheduled_credentials is None and active["_owner"] == owner and active["mode"] == mode and active["security_keys"] == keys
                        and active.get("position_scope","open") == position_scope and active.get("refresh_policy","missing") == refresh_policy):
                    return self._public(active)
                raise HTTPException(409,"enrichment_busy")
            cleanup=None
            if scheduled_credentials:
                headers,cleanup=scheduled_credentials()
            forwarded={k:v for k,v in headers.items() if k.lower() in {"cookie","authorization","x-csrf-token"}}
            try:
                captured=self.evidence.candidates(position_scope=position_scope,security_keys=keys,refresh_policy=refresh_policy)["items"]
                # A valid selected listing whose fields are already complete
                # has no work under missing/stale policy, rather than an invalid
                # identity. Registration and selected scope remain mandatory.
                registered=(self.evidence.candidates(position_scope=position_scope,security_keys=keys,refresh_policy="refresh_existing")["items"]
                    if keys and set(keys)-{c["security_key"] for c in captured} else captured)
            except Exception:
                if cleanup:
                    cleanup()
                raise
            if keys and set(keys)-{c["security_key"] for c in registered}:
                if cleanup:
                    cleanup()
                raise HTTPException(422,"invalid_retrieval_candidate")
            cursor_key=(owner,position_scope,refresh_policy)
            offset=(self._cursors.get(cursor_key,0) if batch_offset is None else max(0,int(batch_offset))) % max(1,len(captured)) if keys is None else 0
            targets=(captured[offset:]+captured[:offset])[:MAX_SELECTED]
            job={"request_id":str(uuid4()),"status":"queued","code":"queued","created_at":_now(),"finished_at":None,
                "mode":mode,"security_keys":keys,"position_scope":position_scope,"refresh_policy":refresh_policy,
                "progress":{"stage":"queued","completed":0,"total":0,"current_security":None},
                "outcomes":[],"counts":{"api_requests":0,"model_requests":0,"rest_requests":0,"web_requests":0},
                "coverage":{"total_candidates":len(captured),"selected":len(targets),"remaining":max(0,len(captured)-len(targets)),"truncated":len(captured)>len(targets),
                            "batch_offset":offset,"next_batch_offset":(offset+len(targets))%max(1,len(captured))},
                "per_request_limits":{"model":8,"rest":8,"web":8,"selected":MAX_SELECTED},
                "portfolio_refresh_required":False,"failure":None,"children":[],"parent_request_id":parent_request_id,
                "_owner":owner,"_targets":deepcopy(targets)}
            self._jobs[job["request_id"]]=job
            self._event(job,"retrieval_queued",selected=len(targets))
            for old in [k for k,j in self._jobs.items() if j["status"] not in {"queued","running"}][:-97]:
                self._jobs.pop(old,None)
        def work():
            try:
                self.run(job["request_id"],forwarded,language)
            finally:
                if cleanup:
                    cleanup()
        try:
            self.worker_factory(target=work,daemon=True,name="risk-input-retrieval").start()
            if keys is None:
                self._cursors[cursor_key]=job["coverage"]["next_batch_offset"]
        except Exception as exc:
            if cleanup:
                cleanup()
            with self._lock:
                job.update(status="failed",code="job_failed",failure={"code":"job_failed","stage":"queued","error_type":type(exc).__name__},finished_at=_now())
                self._event(job,"retrieval_failed",failure=job["failure"])
            raise
        return self._public(job)

    def _wait(self,jobs,child,owner,job=None):
        deadline=time.monotonic()+900
        while child.get("status") in {"queued","running"}:
            if time.monotonic()>deadline:
                raise HTTPException(504,"request_limit")
            time.sleep(self.poll_seconds)
            child=jobs.get(child["request_id"],owner)
            if job is not None:
                with self._lock:
                    job["children"]=[snapshot(child,branch="risk_ai",parent_request_id=job["request_id"])]
                    job["counts"].update({key:child.get("counts",{}).get(key,0) for key in ("model_requests","rest_requests","web_requests")})
        return child

    def _authorize(self,identifier,headers):
        """Recheck the original actor/token and write permission via fixed REST."""
        if self.app is None:
            raise HTTPException(401,"owner_not_authorized")
        async def request():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url="https://portfolio-internal",follow_redirects=False) as client:
                return await client.post(PREFIX+"/"+identifier+"/authorize",headers=headers)
        response=asyncio.run(request())
        if response.status_code != 200:
            raise HTTPException(401,"owner_not_authorized")

    def run(self,identifier,headers,language):
        job=self._jobs[identifier]
        try:
            with self._lock:
                job.update(status="running",code="running")
                self._event(job,"retrieval_started")
            self._authorize(identifier,headers)
            candidates=deepcopy(job["_targets"])
            job["progress"]["total"]=len(candidates)
            unresolved=[]
            for candidate in candidates:
                with self._lock:
                    job["progress"].update(stage="api" if job["mode"] != "ai" else "ai",current_security={k:candidate.get(k) for k in ("security_key","symbol")})
                    self._event(job,"security_started",**{k:candidate.get(k) for k in ("security_key","symbol")})
                result={"security_key":candidate["security_key"],"symbol":candidate["symbol"],"status":"unavailable","code":"data_unavailable",
                    "available_fields":[],"missing_fields":candidate["missing_fields"],"sources":[],"attempted":False,
                    "api":{"status":"not_attempted","code":"not_requested"},"ai":{"status":"not_attempted","code":"not_requested"}}
                if job["mode"] != "ai":
                    self._authorize(identifier,headers)
                    try:
                        api=self.evidence.api_sources.fetch(self.evidence.inputs.candidate(candidate["security_key"]))
                    except Exception as exc:
                        api={"records":[],"sources":[],"requests":0,"status":"unavailable","code":"provider_unavailable"}
                        self._event(job,"api_failed",code="provider_unavailable",error_type=type(exc).__name__,security_key=candidate["security_key"],symbol=candidate["symbol"])
                    job["counts"]["api_requests"]+=api["requests"]
                    result["attempted"] |= api["requests"] > 0
                    self._authorize(identifier,headers)
                    if api["records"]:
                        try:
                            self.evidence.inputs.publish_evidence(candidate,api["records"],expected_revision=candidate["expected_revision"])
                            self.evidence.changed()
                        except HTTPException:
                            api.update(records=[],sources=[],status="unavailable",code="identity_changed")
                    result["api"]={"status":api["status"],"code":api["code"]}
                    result["available_fields"].extend(r["field"] for r in api["records"])
                    result["sources"].extend({"url":s["url"],"source_kind":s["source_kind"],"retrieved_at":s["retrieved_at"],
                        "as_of":s.get("as_of"),"fields":s["fields"]} for s in api["sources"])
                    self._event(job,"api_finished",code=api["code"],security_key=candidate["security_key"],symbol=candidate["symbol"],
                        record_count=len(api["records"]),source_count=len(api["sources"]))
                risk=self.evidence.inputs.read(self.evidence.inputs.candidate(candidate["security_key"]))
                remaining=missing_fields(risk,candidate)
                if (remaining or job["refresh_policy"] == "refresh_existing") and job["mode"] != "api" and result["api"]["code"] != "identity_changed":
                    unresolved.append(candidate["security_key"])
                risk=self.evidence.inputs.read(self.evidence.inputs.candidate(candidate["security_key"]))
                result["missing_fields"]=missing_fields(risk,candidate)
                result["available_fields"]=sorted(set(result["available_fields"]))
                result["status"]=("updated" if not result["missing_fields"] else "partial") if result["available_fields"] else "unavailable"
                result["code"]="data_found" if result["status"]=="updated" else "partial_data" if result["status"]=="partial" else "data_unavailable"
                with self._lock:
                    job["outcomes"].append(result)
                    job["portfolio_refresh_required"] |= bool(result["available_fields"])
                    job["progress"]["completed"]+=1
                    self._event(job,"security_api_finished",security_key=candidate["security_key"],symbol=candidate["symbol"],
                        available_fields_count=len(result["available_fields"]),missing_fields_count=len(result["missing_fields"]))
            # One child shares the existing total budgets across the entire
            # bounded selected set. API failure never skips eligible AI fallback.
            child=None
            if unresolved:
                self._authorize(identifier,headers)
                job["progress"].update(stage="ai",completed=0)
                options={}
                if job["position_scope"] != "open":
                    options["position_scope"]=job["position_scope"]
                if job["refresh_policy"] != "missing":
                    options["candidate_options"]={"refresh_policy":job["refresh_policy"]}
                if hasattr(self.ai_jobs,"diagnostics"):
                    options["parent_request_id"]=identifier
                self._event(job,"ai_starting",selected=len(unresolved))
                child=self.ai_jobs.start(job["_owner"],headers,language,security_keys=unresolved,**options)
                with self._lock:
                    job["children"]=[snapshot(child,branch="risk_ai",parent_request_id=identifier)]
                    self._event(job,"ai_started",child_request_id=child["request_id"])
                child=self._wait(self.ai_jobs,child,job["_owner"],job)
                with self._lock:
                    job["children"]=[snapshot(child,branch="risk_ai",parent_request_id=identifier)]
                    self._event(job,"ai_finished",child_request_id=child["request_id"],code=child.get("code"),failure=child.get("failure"))
                for field in ("model_requests","rest_requests","web_requests"):
                    job["counts"][field]=child.get("counts",{}).get(field,0)
                self._authorize(identifier,headers)
                for result in job["outcomes"]:
                    if result["security_key"] not in unresolved:
                        continue
                    outcome=next((r for r in child.get("outcomes",[]) if r.get("security_key")==result["security_key"]),{})
                    result["attempted"] |= bool(outcome.get("attempted"))
                    result["available_fields"]=sorted(set(result["available_fields"])|set(outcome.get("available_fields",[])))
                    result["sources"].extend(outcome.get("sources",[]))
                    result["ai"]={"status":child["status"],"code":outcome.get("code") or child.get("code","data_unavailable"),
                        "request_id":child["request_id"],"failure":safe_failure(child.get("failure")),"counts":deepcopy(child.get("counts",{}))}
                    if outcome.get("diagnostic") or child.get("failure"):
                        result["diagnostic"]=safe_failure({**(outcome.get("diagnostic") or child.get("failure") or {}),
                            "child_request_id":child["request_id"],"child_status":child["status"],"child_failure":child.get("failure")})
                    current=self.evidence.inputs.read(self.evidence.inputs.candidate(result["security_key"]))
                    candidate=next(c for c in candidates if c["security_key"]==result["security_key"])
                    result["missing_fields"]=missing_fields(current,candidate)
                    result["status"]=("updated" if not result["missing_fields"] else "partial") if result["available_fields"] else "unavailable"
                    result["code"]="data_found" if result["status"]=="updated" else "partial_data" if result["status"]=="partial" else result["ai"]["code"]
                    job["portfolio_refresh_required"] |= bool(outcome.get("available_fields"))
            with self._lock:
                failed=child and child.get("status")=="failed"
                diagnostic=safe_failure({**(child.get("failure") or {}),"code":child.get("code") or "job_failed",
                    "stage":(child.get("failure") or {}).get("stage") or "ai","branch":"risk_ai", "child_request_id":child["request_id"],
                    "child_status":child["status"],"child_failure":child.get("failure")}) if failed else None
                job.update(status="failed" if failed else "completed",code=child.get("code","job_failed") if failed else "completed",failure=diagnostic,finished_at=_now())
                self._event(job,"retrieval_failed" if failed else "retrieval_completed",failure=diagnostic)
                job["progress"].update(stage=job["status"],completed=len(candidates),current_security=None)
        except Exception as exc:
            with self._lock:
                code=exc.detail if isinstance(exc,HTTPException) and isinstance(exc.detail,str) else "job_failed"
                current=job["progress"].get("current_security") or {}
                child=(job.get("children") or [{}])[-1]
                diagnostic=safe_failure({"code":code,"stage":job["progress"]["stage"],"error_type":type(exc).__name__,
                    "security_key":current.get("security_key"),"symbol":current.get("symbol"),"child_request_id":child.get("request_id"),
                    "child_status":child.get("status"),"child_failure":child.get("failure")})
                job.update(status="failed",code=code,failure=diagnostic,finished_at=_now())
                self._event(job,"retrieval_failed",failure=diagnostic)
                job["progress"].update(stage="failed",current_security=None)

    def router(self):
        router=APIRouter(tags=["risk input retrieval"])
        @router.get(PREFIX+"/candidates")
        def candidates(request:Request,position_scope:str="open",refresh_policy:str="missing"):
            _user(request)
            rows=self.evidence.candidates(position_scope=position_scope,refresh_policy=refresh_policy)
            allowed={"security_key","symbol","stock_market","currency","name","identity_token","missing_fields","api_supported_fields","ai_supported_fields"}
            return {"items":[{k:v for k,v in row.items() if k in allowed} for row in rows["items"]],"total_count":rows["total_count"]}
        @router.post(PREFIX,status_code=202)
        def start(request:Request,payload:RetrievalStart|None=None):
            actor=_user(request,True)
            payload=payload or RetrievalStart()
            language=payload.language or ("he" if request.headers.get("Accept-Language","").startswith("he") else "en")
            return self.start(actor["id"],dict(request.headers),language,security_keys=payload.security_keys,mode=payload.mode,
                position_scope=payload.position_scope,refresh_policy=payload.refresh_policy)
        @router.get(PREFIX+"/status")
        def status(request:Request):
            return self.status(_user(request)["id"])
        @router.get(PREFIX+"/{request_id}")
        def get(request_id:str,request:Request):
            return self.get(request_id,_user(request)["id"])
        @router.post(PREFIX+"/{request_id}/authorize")
        def authorize(request_id:str,request:Request):
            self.get(request_id,_user(request,True)["id"])
            return {"authorized":True}
        return router


class RiskInputRetrievalSchedules:
    def __init__(self,reader,writer,scheduler_getter,auth_store,retrieval,*,timezone="UTC"):
        self.reader,self.writer,self.scheduler_getter,self.auth_store,self.retrieval=reader,writer,scheduler_getter,auth_store,retrieval
        self.timezone,self._lock=timezone,RLock()

    def settings(self):
        raw=self.reader() or {}
        return {"enabled":raw.get("enabled") is True,"mode":raw.get("mode","api_then_ai"),"security_keys":raw.get("security_keys"),
            "schedule_config":deepcopy(raw.get("schedule_config") or {"frequency":"weekly","weekdays":[0],"hour":8,"minute":0}),
            "timezone":raw.get("timezone") or self.timezone,"language":raw.get("language","en"),"owner_id":raw.get("owner_id","")}

    def status(self):
        result=self.settings()
        result.pop("owner_id",None)
        replacement=getattr(self,"replacement",None)
        if replacement and replacement.is_migrated():
            row=replacement.legacy_status("risk_inputs")
            return {**result, **{key:(row or {}).get(key) for key in ("next_run","last_run_at","last_run_code","last_request_id")}}
        scheduler=self.scheduler_getter()
        job=scheduler.get_job(JOB_ID) if scheduler else None
        result["next_run"]=job.next_run_time.isoformat() if job and job.next_run_time else None
        raw=self.reader() or {}
        result.update({key:raw.get(key) for key in ("last_run_at","last_run_code","last_request_id")})
        return result

    @staticmethod
    def _validate(settings):
        if (type(settings["enabled"]) is not bool or settings["mode"] not in MODES or settings["language"] not in {"en","he"}
                or settings["schedule_config"].get("frequency") not in {"daily","weekly","monthly"}):
            raise ValueError("invalid_schedule")
        keys=settings["security_keys"]
        if keys is not None and (not isinstance(keys,list) or not 1<=len(keys)<=3 or any(not isinstance(k,str) or not 1<=len(k)<=300 for k in keys)):
            raise ValueError("invalid_schedule")
        settings["schedule_config"]=normalize_schedule(settings["schedule_config"])
        return schedule_trigger(settings["schedule_config"],settings["timezone"])

    def update(self,actor,payload):
        if not isinstance(actor,dict) or actor.get("role") not in {"Admin","Operator"}:
            raise HTTPException(403,"read_only")
        if not isinstance(payload,dict) or set(payload)-{"enabled","mode","security_keys","schedule_config","timezone","language"}:
            raise HTTPException(400,"invalid_schedule")
        with self._lock:
            settings=self.settings()
            settings.update(deepcopy(payload))
            try:
                self._validate(settings)
            except (ValueError,TypeError,KeyError,AttributeError,ZoneInfoNotFoundError):
                raise HTTPException(400,"invalid_schedule") from None
            settings["owner_id"]=actor["id"]
            self.writer(settings)
            replacement=getattr(self,"replacement",None)
            if replacement and replacement.is_migrated():
                replacement.import_legacy("risk_inputs")
            self.configure()
            return self.status()

    def configure(self):
        with self._lock:
            replacement=getattr(self,"replacement",None)
            if replacement and replacement.is_migrated():
                replacement.configure()
                return
            scheduler=self.scheduler_getter()
            if not scheduler:
                return
            try:
                scheduler.remove_job(JOB_ID)
            except Exception:
                pass
            settings=self.settings()
            if settings["enabled"]:
                try:
                    trigger=self._validate(settings)
                except (ValueError,TypeError,KeyError,AttributeError,ZoneInfoNotFoundError):
                    return
                scheduler.add_job(self.run,trigger,id=JOB_ID,replace_existing=True,max_instances=1,coalesce=True,misfire_grace_time=60)

    def run(self):
        settings=self.settings()
        if not settings["enabled"]:
            return
        def credentials():
            token,csrf=self.auth_store.scheduled_session(settings["owner_id"])
            return {"cookie":f"{SESSION_COOKIE_NAME}={token}","x-csrf-token":csrf},lambda:self.auth_store.logout(token)
        try:
            self._validate(settings)
            raw=self.reader() or {}
            child=self.retrieval.start(settings["owner_id"],{},settings["language"],mode=settings["mode"],security_keys=settings["security_keys"],
                scheduled_credentials=credentials,batch_offset=int(raw.get("batch_cursor") or 0))
            code,request_id="queued",child["request_id"]
            cursor=child.get("coverage",{}).get("next_batch_offset",0)
        except (HTTPException,PermissionError,ValueError,TypeError,KeyError,AttributeError,ZoneInfoNotFoundError) as exc:
            code="owner_not_authorized" if isinstance(exc,PermissionError) else "enrichment_busy" if isinstance(exc,HTTPException) and exc.status_code==409 else "invalid_schedule"
            request_id,cursor=None,None
        with self._lock:
            current=self.reader() or {}
            if current.get("owner_id") != settings["owner_id"]:
                return
            current.update(last_run_at=_now(),last_run_code=code,last_request_id=request_id)
            if cursor is not None and settings["security_keys"] is None:
                current["batch_cursor"]=cursor
            self.writer(current)

    def router(self):
        router=APIRouter(tags=["risk input retrieval schedule"])
        @router.get(SCHEDULE_ENDPOINT)
        def get(request:Request):
            _user(request)
            return self.status()
        @router.put(SCHEDULE_ENDPOINT)
        def update(request:Request,payload:dict):
            return self.update(_user(request,True),payload)
        return router
