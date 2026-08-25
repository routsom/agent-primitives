import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";
import mermaid from "astro-mermaid";

export default defineConfig({
  site: "https://routsom.github.io",
  base: "/agent-primitives",
  integrations: [
    // Must come before starlight() - see astro-mermaid's integration-order requirement.
    mermaid({ theme: "neutral", autoTheme: true }),
    starlight({
      title: "agent-primitives",
      description: "A framework-free, multi-LLM boilerplate for building production multi-agent systems.",
      social: [{ icon: "github", label: "GitHub", href: "https://github.com/routsom/agent-primitives" }],
      editLink: {
        baseUrl: "https://github.com/routsom/agent-primitives/edit/main/docs/",
      },
      sidebar: [
        { label: "Overview", link: "/" },
        { label: "Architecture", link: "/architecture/" },
        {
          label: "Getting started",
          items: [
            { label: "Quickstart: TypeScript", link: "/quickstart-ts/" },
            { label: "Quickstart: Python", link: "/quickstart-py/" },
          ],
        },
        {
          label: "Concepts",
          items: [
            { label: "Providers (multi-LLM)", link: "/providers/" },
            { label: "Harness", link: "/harness/" },
            { label: "MCP", link: "/mcp/" },
            { label: "A2A", link: "/a2a/" },
            { label: "Tracing", link: "/tracing/" },
            { label: "Evals", link: "/evals/" },
          ],
        },
        {
          label: "Operating it",
          items: [
            { label: "Deployment", link: "/deploy/" },
            { label: "Security", link: "/security/" },
          ],
        },
        { label: "Claude Code integration", link: "/claude-code/" },
      ],
    }),
  ],
});
