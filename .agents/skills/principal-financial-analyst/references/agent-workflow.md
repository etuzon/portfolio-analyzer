# Agent Relationships

The coordinator owns scope and handoffs. Dedicated role agents communicate
directly for needed evidence and contracts, report consequential decisions to the
coordinator, and return defects to their owner. QA starts from requirements and
raw evidence independently. Supporting financial skills are loaded by the analyst;
they are not additional agents. Schedule phases within the available active slots.

```mermaid
flowchart TD
    User[User] --> Coordinator[Main agent: coordinate scope and handoffs]
    Coordinator --> Finance[Financial Research agent]
    Coordinator --> UX[UX agent]
    Coordinator --> Dev[Development owner or agent]
    Coordinator --> QA[Fresh independent QA agent]
    Finance <-->|Financial definitions, sources, examples| Dev
    Finance <-->|Units, scope, meaning, uncertainty| UX
    UX <-->|Interaction and API contracts| Dev
    QA -->|Financial-method findings| Finance
    QA -->|Usability findings| UX
    QA -->|Implementation findings| Dev
    Finance -->|Evidence and open decisions| Coordinator
    UX -->|Design and review| Coordinator
    Dev -->|Implementation and checks| Coordinator
    QA -->|Independent verdict and gaps| Coordinator
    Coordinator -->|Material decisions or missing authorization| User
```

For financial implementation: financial contract and UX where relevant, then
development, financial re-check, and independent QA. Re-test changed behavior
after findings. Pure financial research can finish without an engineering cycle.
Cosmetic-only edits use focused review. Research/QA readiness grants no release
authority; existing explicit authorization remains valid for its scope.
