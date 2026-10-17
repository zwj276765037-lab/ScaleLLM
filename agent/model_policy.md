# Model policy

Desired settings are not proof of actual runtime settings.
Normalize the latest user instruction into configuration, clearing conflicting more-specific overrides when needed.
Record actual runtime settings only from runtime evidence; never silently substitute a model.

<!-- research-agent:desired-models:begin -->
## Desired model configuration

These are requested launch settings; actual runtime remains unverified.
Precedence: built-in role fallback → project → explicit role → small mission → agent → current launch override.

| Scope | Identity | Desired model | Reasoning effort |
|---|---|---|---|
| built-in fallback | controller | gpt-6-astra | xhigh |
| built-in fallback | research | gpt-6-astra | xhigh |
| built-in fallback | engineering | gpt-6-sol | max |
| role | engineering | gpt-6.1-sol | xhigh |

Normalize each new user instruction into configuration and update conflicting specific overrides when needed. Files do not change already-running sessions.
<!-- research-agent:desired-models:end -->
