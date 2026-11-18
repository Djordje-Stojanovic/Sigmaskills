# Financial Services pack setup

Source: [anthropics/financial-services](https://github.com/anthropics/financial-services).

- The data comes through MCP servers declared in `plugins/vertical-plugins/financial-analysis/.mcp.json`: Daloopa, Morningstar, S&P Global (Kensho), FactSet, Moody's, MT Newswires, Aiera, LSEG, PitchBook, Chronograph, Egnyte, Box.
- Each provider may need a subscription or API key from that provider; the source gives no key names. LSEG needs MCP credentials and data entitlements; S&P Global needs a Capital IQ Pro or Kensho subscription. The owner signs in; the agent never does.
- In Claude Code, the source's own route is the plugin marketplace: `claude plugin marketplace add anthropics/financial-services`, then the `financial-analysis` plugin first. Offer it only when the owner wants the data connectors.
- Without any connector the skills still work on numbers the owner gives. For SEC filings, SigmaFinanceMan needs no subscription.
