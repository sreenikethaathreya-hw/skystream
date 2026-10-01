"""Every tool the agent can call, in one list. Read tools never write; ACTION_TOOLS pass through WriteGuardPlugin."""

from app.ai.data_agent.actions import ACTION_TOOLS
from app.ai.data_agent.admin_tools import ADMIN_TOOLS
from app.ai.data_agent.lead_tools import LEAD_TOOLS
from app.ai.data_agent.rep_tools import REP_TOOLS
from app.ai.data_agent.tools import TOOLS

ALL_TOOLS = [*TOOLS, *REP_TOOLS, *LEAD_TOOLS, *ADMIN_TOOLS, *ACTION_TOOLS]
