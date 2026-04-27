# Architecture Diagram Spec

> Contract between the Architect agent and the visualization viewer.
> The Architect writes JSON files conforming to this spec.
> The viewer reads them. Neither side changes this without both agreeing.

## File Location Convention

```
.architecture/
  system.json           ← always exists, zoom: system
  components/
    [name].json         ← zoom: component
  flows/
    [name].json         ← zoom: flow
  data/
    [name].json         ← zoom: data
```

## Base Shape (all zoom types)

```json
{
  "title": "Human readable name",
  "zoom": "system | component | flow | data",
  "status": "proposed | current"
}
```

## Zoom: system / component

Used for: system context diagrams and component connection diagrams.

```json
{
  "title": "System Context",
  "zoom": "system",
  "status": "current",
  "nodes": [
    {
      "id": "unique-id",
      "label": "Display Name",
      "type": "service | database | client | external | component",
      "drilldown": "components/name.json"
    }
  ],
  "edges": [
    {
      "from": "node-id",
      "to": "node-id",
      "label": "optional description",
      "type": "sync | async | return | data"
    }
  ]
}
```

## Zoom: flow

Used for: sequence diagrams — ordered interactions between actors.

```json
{
  "title": "Auth Flow",
  "zoom": "flow",
  "status": "current",
  "nodes": [
    { "id": "user", "label": "User", "type": "actor" },
    { "id": "api",  "label": "API", "type": "service" }
  ],
  "steps": [
    { "from": "user", "to": "api",  "label": "login request", "type": "sync" },
    { "from": "api",  "to": "user", "label": "token",         "type": "return" }
  ]
}
```

Steps are rendered in order with numbered labels. Use `steps` not `edges` for flow diagrams.

## Zoom: data

Used for: entity-relationship diagrams and data models.

```json
{
  "title": "User Schema",
  "zoom": "data",
  "status": "current",
  "entities": [
    {
      "id": "User",
      "description": "One row per registered user (auth identity).",
      "fields": [
        { "name": "id",    "type": "string" },
        { "name": "email", "type": "string" }
      ]
    }
  ],
  "relations": [
    {
      "from": "User",
      "to": "Order",
      "label": "has",
      "cardinality": "one-to-many"
    }
  ]
}
```

## Node Types

| Type        | Use For                          | Shape      |
|-------------|----------------------------------|------------|
| `service`   | APIs, microservices, servers     | Rounded rect (blue) |
| `database`  | Databases, caches, stores        | Barrel (amber) |
| `client`    | Browsers, mobile apps, CLIs      | Rounded rect (green) |
| `external`  | Third-party systems              | Rounded rect (gray) |
| `component` | Internal modules, packages       | Rounded rect (purple) |
| `entity`    | Data model entities              | Rectangle (teal) |
| `actor`     | People, users, roles in flows    | Rounded rect (pink) |

## Edge Types

| Type     | Renders As     | Use For                        |
|----------|----------------|--------------------------------|
| `sync`   | Solid arrow    | Synchronous calls              |
| `async`  | Dashed arrow   | Async messages, events, queues |
| `return` | Faint dashed   | Response values                |
| `data`   | Dotted no-head | Data relationships             |

## Drilldown Convention

Any node can link to a child diagram:
```json
{ "id": "api", "label": "API Gateway", "drilldown": "components/api.json" }
```

Paths are relative to the `.architecture/` root.
Nodes with a drilldown render with a solid border and show "↓ click to drill down" on hover.

## Status Meanings

| Status     | Meaning                                           |
|------------|---------------------------------------------------|
| `current`  | Reflects what is actually built                   |
| `proposed` | Design intent — workers should conform to this    |
