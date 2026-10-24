# Public dashboard boundary

Reads expose research derived from the cited public FRED, FDIC, and SEC sources. Mutating routes require an operator bearer token configured as `MARKETS_ADMIN_TOKEN`; without it all writes are disabled. Keep that token on the server/operator client, never in a static dashboard bundle. The model is research and does not provide investment advice. Public availability does not establish redistribution rights for every third-party series; consult each source series' terms before republishing underlying data.
