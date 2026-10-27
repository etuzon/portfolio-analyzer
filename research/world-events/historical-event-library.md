# Historical event library

Research date: 27/10/2026. Eight event groups and 29 instrument cases were added
to the existing Brazil election examples. The library now contains 38 cases,
nine distinct event IDs and nine exposure maps. These are deliberately selected
historical examples, not a representative dataset for forecasting.

The dates below identify the measured market sessions. Except for Delta's annual
results discussed separately, percentages are source-reported changes from the
previous regular-session close. They retain the source's rounding and have not
been recomputed from independently retrieved adjusted prices. No baseline prices
were invented. Returns quoted in different currencies or at different exchange
closing times are not synchronized USD portfolio returns.

| Event / measured session | Observed examples | Exposure link recorded |
| --- | --- | --- |
| Pandemic selloff, 16/03/2020 | S&P 500 −11.98%; Nasdaq −12.32%; S&P real estate −16.5%; consumer staples −7.0%. [Reuters](https://www.investing.com/news/stock-market-news/another-black-monday-as-coronavirus-response-upends-wall-street-2111230) | Activity and liquidity stress affected broad equities; relative resilience did not mean a positive return. |
| Vaccine news, 09/11/2020 | Pfizer +7.7%; Carnival approximately +39%; Delta approximately +17%; Zoom −17.4%. [ABC News](https://abcnews.com/Business/dow-surges-1500-points-vaccinea-hopes/story?id=74104964) | Reopening expectations supported travel while reducing the premium for lockdown beneficiaries. |
| Brexit result, 24/06/2016 | European banks −14.5%; STOXX 600 −7.0%; FTSE 100 approximately −3.2%; Fresnillo +11.8%. [Reuters](https://www.business-standard.com/article/reuters/banks-plunge-as-brexit-vote-sends-european-shares-reeling-116062401411_1.html) | Political/trade uncertainty crossed borders; gold exposure provided a contrasting response. |
| Japan earthquake/nuclear crisis, 14–15/03/2011 | On 14/03, TEPCO −23.6% and Kajima +22.2%. [Reuters](https://m.investing.com/news/forex-news/japan-markets-after-quake%2C-topix-suffers-biggest-drop-in-2-years-201295?ampMode=1). On 15/03, Nikkei 225 −10.55%. [Index-provider history](https://indexes.nikkei.co.jp/70th/adayintokyomarket-article.html) | Physical disruption hurt the utility while expected rebuilding orders supported construction. The next-day index loss is kept as a separate session. |
| Saudi oil-facility attack, 16/09/2019 | S&P energy +3.3%; Apache +16.9%; American Airlines −7.3%. [Reuters](https://uk.investing.com/news/stock-market-news/beleaguered-us-energy-shares-soar-after-attacks-on-saudi-facilities-1963509) | Saudi supply disruption transmitted through oil prices to US producers and fuel buyers with opposite signs. |
| Russia invasion/sanctions, 24/02/2022 | MOEX regular close −33.3%; STOXX 600 −3.28%; S&P 500 +1.5%. [Reuters—Russia](https://www.marketscreener.com/news/latest/Russia-s-rouble-hits-record-low-as-Ukraine-attack-prompts-more-Western-sanctions-39576219/), [Anadolu—Europe](https://www.aa.com.tr/en/economy/global-markets-in-red-with-rising-risks-amid-russian-intervention-in-ukraine/2513882), [Morgan Stanley—US](https://www.morganstanley.com/campaigns/wealth-management/move-report/move-report2022feb24/) | Financial restrictions and regional exposure differed; the US market reversed initial losses. Moscow additional-session prices are excluded. |
| US banking stress, 13/03/2023 | First Republic approximately −62%; European banks −5.7%; Commerzbank −12.7%. [FDIC retrospective](https://www.fdic.gov/news/speeches/2023/spmay1523.html), [Reuters—Europe](https://www.koha.net/en/bote/bideni-premton-stabilitet-me-gjithe-falimentimin-e-dy-bankave) | Depositor confidence and funding pressure spread across banking markets; depositor guarantees did not guarantee shareholder protection. |
| DeepSeek repricing, 27/01/2025 | Nvidia −16.9%; Broadcom −17.4%; Vistra −28.3%; Dow +0.7%. [AP](https://apnews.com/article/52c54e361616509280bd2775674b6b4b), [Reuters](https://ca.investing.com/news/economy-news/chinas-deepseek-sets-off-ai-market-rout-3806924?ampMode=1) | A China-origin technology surprise affected US compute and power-demand expectations; the selloff did not describe every stock. |

Each exposure map includes conditions and offsets. Producer output, fuel hedges,
company liquidity, policy support, actual customer demand, and index composition
can change an outcome. The maps do not say that every war, election, bank failure
or technology release has the same effect. Cross-border links without measured
foreign-stock evidence remain explicitly qualitative.

## Event verification and timing

The cases link market observations to dated primary evidence:

- [WHO, 11/03/2020](https://www.who.int/news-room/speeches/item/who-director-general-s-opening-remarks-at-the-media-briefing-on-covid-19---11-march-2020) and [Federal Reserve, 15/03/2020](https://www.federalreserve.gov/newsevents/pressreleases/monetary20200315a.htm).
- [Pfizer/BioNTech interim announcement, 09/11/2020](https://www.pfizer.com/news/press-release/press-release-detail/pfizer-and-biontech-announce-vaccine-candidate-against).
- [Bank of England statement, 24/06/2016](https://www.bankofengland.co.uk/news/2016/june/statement-from-the-governor-of-the-boe-following-the-eu-referendum-result).
- [Nikkei's retrospective event chronology](https://indexes.nikkei.co.jp/70th/adayintokyomarket-article.html).
- [Aramco confirmation, 14/09/2019](https://www.aramco.com/en/news-media/news/2019/incidents-at-abqaiq-and-khurais).
- [US Treasury sanctions, 24/02/2022](https://home.treasury.gov/news/press-releases/jy0608).
- [FDIC closure/response statement, 13/03/2023](https://www.fdic.gov/news/press-releases/2023/pr23019.html).
- [Original DeepSeek-R1 paper, 22/01/2025](https://arxiv.org/abs/2501.12948v1), preceding the later repricing session. The paper does not establish a future collapse in hardware demand.

Primary evidence confirms the event or disclosed facts; it does not establish
the exact portion of a stock move caused by the event. Later regulatory accounts
and company results are retrospective evidence, not information available for
an earlier forecast. The vaccine episode and initial pandemic selloff share
the `covid19-pandemic` family and are not assumed independent observations.

## Revenue and profit are separate outcomes

Delta reported FY2020 GAAP operating revenue of $17,095 million versus $47,007
million in FY2019: a calculated decline of 63.63%, reported by the company as
64% after rounding. GAAP net income moved from +$4,767 million to −$12,385
million, an absolute deterioration of $17,152 million. The record identifies a
profit-to-loss transition and withholds a conventional profit-growth percentage.
[Delta results, published 14/01/2021](https://ir.delta.com/news/news-details/2021/Delta-Air-Lines-Announces-December-Quarter-and-Full-Year-2020-Financial-Results/default.aspx).

These annual results include the whole year's activity, assistance, restructuring
and other factors. They are not attributed solely to the 16/03/2020 stock-market
session, nor converted into a future revenue-loss probability.

## Retrieval

Use `get_event_impact_events` for the compact index. Request a relevant `event_id`
or `symbol` from `get_event_impact_cases`; detail pages contain at most five cases.
Continue with `next_offset` until null before claiming to have reviewed the whole
filtered group. Every record keeps sources, measurement basis, missing data,
competing explanations and unknown forecast percentages. No model was trained.
