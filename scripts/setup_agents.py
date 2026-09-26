"""Create (or update) the three Re-solve agents in your Foundry project.

Run once after filling in .env:   python -m scripts.setup_agents
Re-run any time you change the instructions; Foundry stores a new version.
"""
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from azure.identity import DefaultAzureCredential

from app import agent_instructions as ins
from app import config


def classifier_tools() -> list:
    """Attach the MCP safety tools only if the MCP server has a public URL."""
    if not config.MCP_PUBLIC_URL:
        return []
    return [MCPTool(
        server_label="re_solve_safety",
        server_url=config.MCP_PUBLIC_URL,
        require_approval="never",
        allowed_tools=["precheck_text", "content_safety_scan", "get_escalation_policy"],
    )]


def main() -> None:
    if not config.FOUNDRY_PROJECT_ENDPOINT:
        raise SystemExit("Set FOUNDRY_PROJECT_ENDPOINT in .env first.")
    project = AIProjectClient(endpoint=config.FOUNDRY_PROJECT_ENDPOINT,
                              credential=DefaultAzureCredential())
    agents = [
        (config.CLASSIFIER_AGENT, ins.CLASSIFIER, classifier_tools(),
         "Decides whether a comment is cyberbullying and how severe it is."),
        (config.REWRITE_AGENT, ins.REWRITER, [],
         "Suggests kinder alternatives that keep the writer's point."),
        (config.ESCALATION_AGENT, ins.ESCALATION, [],
         "Chooses the escalation and writes the user and moderator messages."),
    ]
    for name, instructions, tools, description in agents:
        extra = {"tools": tools} if tools else {}
        definition = PromptAgentDefinition(model=config.MODEL_DEPLOYMENT,
                                           instructions=instructions, **extra)
        agent = project.agents.create_version(agent_name=name, definition=definition,
                                              description=description)
        mcp_note = " (+ MCP tools)" if tools else ""
        print(f"Created {agent.name} version {agent.version}{mcp_note}")
    print("Done. Open the Foundry portal > Agents to see them.")


if __name__ == "__main__":
    main()
