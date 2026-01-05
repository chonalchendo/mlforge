# Research

Help me research a topic using codebase analysis and external documentation.

## Workflow

1. **Understand what I need** - Ask me:
   - Internal codebase understanding?
   - External documentation/best practices?
   - Combination of the above?

2. **Run research in parallel** - Always run concurrently for efficiency:

   ### Codebase Exploration
   Search and analyze the internal codebase:

   **Discovery mode:**
   - Use glob for filename/path searches (e.g., `**/*.test.*`, `**/auth/**/*`)
   - Use grep for content searches (e.g., function definitions, class declarations)
   - Check both filenames and contents
   - Search for variations (singular/plural, synonyms)
   - Look in common locations (`src/`, `lib/`, `api/`, `components/`)

   **Analysis mode:**
   - Start with entry points (exports, handlers, routes)
   - Follow code paths step by step
   - Read each file involved in the flow
   - Trace data transformations
   - Read 2-3 representative files to identify conventions

   **Output format:**
   ```
   ## Codebase Findings

   ### Files Found
   - `path/to/file.ext:line` - Description

   ### Patterns Identified
   - **Pattern name**: Description with file reference

   ### Entry Points
   - `path/to/main.ext:45` - Where to start reading
   ```

   ### External Research
   Fetch and analyze web content:

   **Research targets:**
   - **API/Library docs**: Official documentation, changelogs, examples
   - **Best practices**: Recent articles, recognized experts, cross-reference for consensus
   - **Technical solutions**: Stack Overflow, GitHub issues, exact error messages
   - **Comparisons**: "X vs Y", migration guides, benchmarks

   **Search techniques:**
   - Use quotes for exact phrases: `"error message"`
   - Site-specific searches: `site:docs.example.com`
   - Exclusions: `-unwanted-term`
   - Recency: include year for current info

   **Quality guidelines:**
   - Prioritize official sources and recognized experts
   - Note publication dates and version information
   - Indicate when information is outdated, conflicting, or uncertain

   **Output format:**
   ```
   ## External Findings

   ### [Topic/Source]
   **Source**: [Name with link]
   **Key Points**:
   - Direct quote or finding
   - Additional relevant information

   ### Gaps
   [Missing or uncertain information]
   ```

3. **Synthesize findings** - Combine and analyze:
   - **Codebase**: How it works, file:line references, patterns, architectural decisions
   - **External**: Key concepts, best practices, code examples, pitfalls, doc links
   - **Combined**: Current state vs recommended approach, gap analysis, options with trade-offs

4. **Present results** - Format output as:

   ```
   ## Summary
   [Brief overview]

   ## Codebase Findings
   ### Files Found
   - `path/to/file.ext:line` - Description

   ### Patterns Identified
   - **Pattern name**: Description with file reference

   ## External Findings
   ### [Topic/Source]
   **Source**: [Name with link]
   **Key Points**:
   - Direct quote or finding

   ## Gaps
   [Missing or uncertain information]

   ## Recommendations
   [Actionable next steps]
   ```

## Tips

- Always run codebase and external searches in parallel for efficiency
- Focus on synthesis, not raw data dump
- Include specific references (file:line for code, URLs for docs)
- Note version-specific information
- Indicate when information is outdated, conflicting, or uncertain
