import type { ChatAction } from "@/lib/types";

const ENTRY_KEYS = [["/entries"], ["/consensus/queue"], ["/segments/cube"], ["/reps"]];
const RULE_KEYS = [["/rules"], ["/segments/cube"]];

/** Which cached queries each kind of assistant change makes stale. Unknown kinds refresh everything. */
const KEYS_BY_KIND: Record<string, string[][]> = {
  entry_submitted: ENTRY_KEYS,
  ibp_justified: ENTRY_KEYS,
  entry_approve: ENTRY_KEYS,
  entry_discuss: ENTRY_KEYS,
  entry_challenge: ENTRY_KEYS,
  bulk_approved: ENTRY_KEYS,
  note_added: [["/entries"], ["/consensus/queue"], ["entry-notes"]],
  rule_activated: RULE_KEYS,
  rule_retired: RULE_KEYS,
};

export function queryKeysFor(actions: ChatAction[]): string[][] | "all" {
  const keys = new Map<string, string[]>();
  for (const action of actions) {
    const known = KEYS_BY_KIND[action.kind];
    if (!known) return "all";
    for (const key of known) keys.set(key.join("|"), key);
  }
  return [...keys.values()];
}

const TOOL_LABELS: Record<string, string> = {
  list_segments: "Listing your segments",
  get_segment_baseline: "Reading the segment baseline",
  get_monthly_series: "Reading plan and actuals by month",
  list_demand_entries: "Reading entries",
  get_ibp_forecast: "Reading the IBP numbers",
  get_competitor_shares: "Reading competitor shares",
  get_rep_track_records: "Reading track records",
  list_lead_rules: "Reading lead rules",
  list_open_exceptions: "Reading the consensus queue",
  sum_segment_figures: "Adding up figures",
  top_segments: "Ranking the top segments",
  get_my_briefing: "Checking what needs attention",
  explain_entry_flags: "Explaining the flags",
  preview_entry_impact: "Running the what-if (not saved)",
  get_market_notes: "Reading market notes",
  get_grower_potential: "Reading grower potential",
  check_justification: "Checking the justification",
  list_claims: "Reading claims",
  lookup_variety: "Looking up the variety",
  get_portfolio_summary: "Summarising the portfolio",
  get_month_close_summary: "Recapping the month close",
  explain_term: "Looking it up in the glossary",
  get_data_status: "Checking data status",
  get_submission_coverage: "Checking coverage",
  get_entry_detail: "Opening the entry",
  get_rep_accuracy_history: "Reading accuracy by month",
  draft_rtb: "Drafting reasons to believe",
  get_supply_export: "Preparing the supply export",
  rank_segments: "Ranking segments",
  summarize_claims: "Grouping claims",
  get_entry_history: "Reading the entry history",
  get_upload_status: "Reading uploads",
  list_user_scopes: "Reading users and scopes",
  get_settings_summary: "Reading settings",
  get_data_quality: "Reading data quality",
  submit_demand_entry: "Submitting your number",
  justify_ibp_entry: "Saving your justification",
  add_entry_note: "Adding the note",
  decide_entry: "Recording the decision",
  bulk_approve_routine: "Approving routine entries",
  compile_lead_rule: "Reading the rule and backtesting it",
  activate_lead_rule: "Activating the rule",
  retire_lead_rule: "Retiring the rule",
};

export function toolLabel(tool: string): string {
  return TOOL_LABELS[tool] ?? tool.replace(/_/g, " ");
}
