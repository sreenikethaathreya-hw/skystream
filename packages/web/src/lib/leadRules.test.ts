import cases from "@fixtures/lead_rule_cases.json";
import { computeImpact } from "./demandMath";
import { evaluateRules } from "./leadRules";
import type { EntryInput, LeadRuleSpec, SegmentContext } from "./mathTypes";

interface RuleCase {
  name: string;
  segmentId: number;
  context: SegmentContext;
  entry: EntryInput;
  rules: LeadRuleSpec[];
  expectedMessages: string[];
}

describe.each(cases as unknown as RuleCase[])("lead rule case: $name", (golden) => {
  it("fires the same rules with the same wording as Python", () => {
    const impact = computeImpact(golden.context, golden.entry);
    const flags = evaluateRules(golden.context, golden.segmentId, golden.entry, impact, golden.rules);
    expect(flags.map((f) => f.message)).toEqual(golden.expectedMessages);
  });
});
