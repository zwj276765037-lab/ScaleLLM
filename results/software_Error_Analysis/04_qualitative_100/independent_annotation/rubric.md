# Independent annotation rubric, v1

Reviewer: A015. Scope: a preselected random sample of 100 fixed-prefix next-token disagreements with reference top1–top2 logit margin below 0.05. This is a local token assessment, not a free-generation, reasoning-chain, task-accuracy, or semantic-equivalence evaluation. Neither candidate is assumed correct.

Read the complete supplied prefix and both decoded candidate tokens for every case. Do not read Root annotations before freezing this independent output. Token strings alone, vocabulary lookup rules, or regular expressions do not determine the label. No unseen continuation is invented.

Each case receives exactly one primary label, one context-specific reason, and confidence high/medium/low in the label itself. Risk flags may overlap and do not indicate a task error.

- **F — local formatting only:** whitespace, case, or an equally narrow presentation difference whose interpretation in this actual context shows no content difference. Punctuation is never automatically harmless; changing boundaries, quotation, list structure, a decimal, or syntax may be substantive. Case that changes an entity or interpretation is not F.
- **W — local wording/grammar choice:** an interpretable lexical or grammatical alternative with no explicit proposition reversal visible in the supplied context. This does not assert strict synonymy or an identical continuation. Articles are assessed for reference/definiteness, not automatically F.
- **C — content may change:** an entity, number, factual attribute, participant/reference, action, or other propositional content may change. I→We is C. This means possible local content change, not a determination that either candidate is false or a task answer is wrong.
- **L — explicit logical/polarity change:** the visible alternative specifically changes negation, polarity, a conditional/causal relation, quantifier scope, or another identifiable logical relation. State the relation; do not use L for general uncertainty or a merely different content word.
- **U — insufficient evidence:** a token fragment, an unresolved alternative completion, or insufficient context prevents a defensible local distinction among the other labels. Incomplete token spelling is not automatically U when the visible context already fixes its relevant meaning.

Decision discipline: first ask whether the supplied evidence is enough; if not, U. If enough, select the most specific visible effect: L for an explicit logical relation, C for possible content/reference changes, W for a defensible local wording/grammar distinction, or narrowly F for presentation only. Ambiguity that could alter the category is documented rather than resolved by treating reference top1 as gold.

Confidence: high means the visible difference supports the selected category directly; medium means it is the best supported category with a stated contextual ambiguity; low means a tentative U or genuinely borderline judgment. Confidence is not a probability of semantic correctness.

Suggested risk flags: token_fragment, unknown_continuation, referent_change, entity_or_number, polarity_or_logic, punctuation_structure, syntax_or_definiteness, casing_or_spacing. Flags require a case-specific reason and are not automatically assigned by string patterns.

Summary will report label counts and unresolved scope. It will not call F/W semantically lossless or C/L task errors, nor extrapolate beyond the selected low-margin disagreement population without a separate statistical argument.
