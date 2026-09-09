# The Great AI Traffic Split: Why Smart Companies Are Routing Between Open and Closed Models

For the last two years, the boardroom AI conversation has revolved around a single question: which model should we bet on? OpenAI or Anthropic? Closed frontier systems or open-weight alternatives from Meta, Alibaba, and DeepSeek? It's the wrong question. The organizations getting the most out of generative AI aren't betting on one model — they're routing intelligently across many, sending each task to whichever model handles it best for the price. Call it the great AI traffic split: a hybrid routing strategy that treats models less like platform decisions and more like a fleet of specialized workers, dispatched by an orchestration layer that decides, request by request, who does the job.

This shift isn't philosophical. It's a direct response to how agentic AI actually behaves in production — and to a cost curve that punishes anyone still routing every request to a single frontier model.

## The Agentic Paradox

Multi-step AI agents are voracious. Anthropic's own engineering team, building the orchestrator-worker architecture behind Claude's Research product, found that agentic workflows consume far more tokens than a simple chat exchange — and multi-agent systems consume dramatically more than that. In Anthropic's data, agents typically use about 4× more tokens than chat interactions, and multi-agent systems use about 15× more tokens than chats.

That token multiplication buys real performance. Anthropic's multi-agent system — a lead agent (Claude Opus 4) orchestrating specialized subagents (Claude Sonnet 4) — outperformed a single-agent Claude Opus 4 setup by 90.2% on Anthropic's internal research evaluation, by decomposing tasks that a single agent solved slowly and sequentially, or missed entirely. But the more striking finding is *why* the gains materialize: in Anthropic's analysis of the BrowseComp evaluation, token usage by itself explains 80% of the performance variance, with the number of tool calls and the choice of model accounting for most of the rest.

That single statistic reframes the economics of agentic AI. If token volume — not just model quality — is the dominant driver of agent performance, then the model you route a given subtask to matters enormously, because every model prices its tokens differently. Running an entire multi-agent pipeline on a single frontier model is like hiring a team of senior partners to do every task in a case file, including the photocopying. It works, but it doesn't scale economically. Once a workflow's token consumption is running at 4–15× the cost basis of a simple chat interaction, the price *per token* stops being a rounding error and becomes the line item finance asks about.

## Three Business Drivers Behind the Split

Three forces are pushing organizations away from single-model deployment and toward routed, hybrid architectures.

**Cost.** The spread between frontier and commodity models is enormous and growing. Enterprises adopting open-weight inference report cost savings of 6× to 60× compared with closed-model pricing for equal or better performance on a given task — Decagon, for instance, cut its inference costs sixfold after moving workloads to Together AI. Separately, engineering analyses of the current market peg the gap between the cheapest usable frontier-class model and the most capable closed model at roughly 100×. Spreads at that scale make it uneconomical to run every task, including trivial classification and formatting calls, through the same expensive endpoint.

**Data sovereignty and regulation.** Regulated industries — financial services, healthcare, government — increasingly need guarantees about where data is processed and retained, which favors open-weight models that can be deployed on-premises or in a private cloud, alongside closed models used for less sensitive tasks. This is precisely why enterprise AI gateways are built to enforce policy at the routing layer rather than leaving compliance to individual application teams.

**Reliability and failover.** Model APIs still go down, get rate-limited, or degrade in quality without warning. A routing layer that can automatically shift traffic to an equivalent model on another provider turns what would be a hard outage into a soft, incremental cost increase rather than a service failure — the same logic that made multi-region and multi-cloud failover standard practice in traditional infrastructure.

## How the Routing Actually Works

In production, "routing" spans a spectrum of sophistication:

- **Orchestrator/executor splits.** A capable, more expensive model plans and delegates; cheaper, faster models execute the individual steps. This mirrors Anthropic's own lead-agent/subagent architecture, generalized to mixed-provider stacks.
- **Learned routers.** RouteLLM, developed by researchers at UC Berkeley, Anyscale, and Canva and published at ICLR 2025, trains a classifier to predict whether a given query needs a strong (expensive) model or can be handled by a weak (cheap) one. Its best-performing router — a matrix-factorization model — achieves 95% of GPT-4's quality on MT Bench using only 26% of the GPT-4 calls a naive approach would require, and that figure drops to 14% of calls when the training data is augmented with LLM-judge labels, translating into cost savings of over 85% on that benchmark. Critically, the researchers found their routers generalize well to other strong-and-weak model pairs without retraining — a property that matters in a market where the model lineup changes monthly.
- **Semantic and complexity routing.** Lightweight classifiers or embedding-similarity checks triage a request by topic or difficulty before it ever reaches a model, sending simple lookups one way and multi-step reasoning another.
- **Live, usage-based multipliers.** Atlassian's Rovo Dev assigns each model a credit multiplier based on its size and capability — a smaller, cost-efficient model might consume a fraction of the credits a frontier model would for the same task — letting the system (or the developer) trade cost against capability in real time.

## The Market Numbers Behind the Shift

The scale of enterprise AI spending makes the stakes clear. Companies spent $37 billion on generative AI in 2025, up from $11.5 billion in 2024 — a 3.2x year-over-year increase, and enterprise infrastructure spending alone (foundation models, training, and tooling) accounted for $18 billion of that total.

Multi-model deployment is now the norm, not the exception. In a survey of 100 enterprise CIOs, 37% of respondents reported using five or more models in production, up from 29% the year before — and the survey's authors attribute this less to avoiding vendor lock-in than to genuine model differentiation by task, since, as one CIO put it, "for most tasks, all the models perform well enough now — so pricing has become a much more important factor."

Open-weight adoption inside enterprises has been more volatile than the "open vs. closed" narrative suggests. Menlo Ventures found that enterprise open-source usage fell from 19% of production AI workloads in late 2024 to 11% in 2025, largely because Meta's Llama — still the most widely adopted open-weight model in the enterprise — has stagnated since last year's Llama 4 release. Yet outside large enterprises, the picture is the opposite: usage benchmarks like vLLM and OpenRouter show rapidly rising adoption of Qwen, DeepSeek, Moonshot/Kimi, MiniMax, and Z AI's GLM among startups and indie developers, suggesting the open-weight wave is real but concentrated in different parts of the market than closed-model incumbents currently serve.

Capital is following the routing thesis. Together AI, whose platform lets companies run open-source models such as DeepSeek, MiniMax, and Kimi more cheaply than closed systems, raised an $800 million Series C in mid-2026 at an $8.3 billion valuation — more than double its prior mark — with annual bookings crossing $1.15 billion as open-source model usage across the industry tripled in twelve months. OpenRouter, the AI gateway that lets developers call over 400 models through a single API, saw its own valuation more than double in under a year, from roughly $547 million to about $1.3 billion, on the back of weekly token volume that grew fivefold in six months. As OpenRouter's CEO put it when announcing the round, "running inference at scale is fundamentally a multi-model problem. The era of picking a single model is over."

## The Vendor Ecosystem

A distinct infrastructure layer has emerged to make hybrid routing practical, including OpenRouter (a model-agnostic gateway spanning 400-plus models), RouteLLM (the open-source, academically benchmarked router), Martian (which focuses on predicting model performance from model internals rather than query features alone), Portkey and Not Diamond (enterprise-grade gateways adding observability, virtual-key management, and predictive model selection), and Together AI (an inference platform specializing in cost-efficient serving of open-weight models). Each occupies a slightly different niche — some prioritize raw model breadth, others prioritize governance and compliance controls, and others prioritize the routing algorithm itself — but all are converging on the same premise: the routing layer, not any single model, is becoming the durable piece of enterprise AI infrastructure.

## Real-World Case Studies

**Atlassian's AI Gateway** is one of the most mature examples of hybrid routing in production. The gateway offers Atlassian's developers a curated "model garden" of 20+ LLMs, audio, and image models from five-plus providers spanning ten-plus model families, supporting more than 100 use cases across eight-plus Atlassian apps. Beyond simplifying integration, the gateway automatically falls back to alternative models or vendors when one provider has an incident — Atlassian reports that this automated fallback has already mitigated multiple production incidents that would otherwise have affected customers. The system also frequently incorporates open-source models where they fit — for instance, using open-source text-to-speech models to transcribe Loom videos for search and summaries, while reserving specific closed frontier models for tasks like contextual document editing.

**Airbnb and Cursor's use of Qwen** illustrates how open-weight models are winning specific, high-volume roles even inside companies that also rely on closed frontier models elsewhere in their stack. Airbnb relies heavily on Qwen for its user-facing AI features, while Cursor uses it as the open-source base for its internal model — decisions that reflect Qwen's competitive performance-per-dollar for well-defined tasks rather than a wholesale rejection of closed models.

## The Risks Nobody Puts on the Slide

Hybrid routing isn't free of downsides, and the same features that make it economically attractive introduce new failure modes:

- **Silent quality regression.** Routing a request to a cheaper model can degrade the response in ways that don't show up on a dashboard — they surface days later as customer complaints, by which point the root cause is difficult to trace back to a specific routing decision.
- **Multi-agent cost compounding.** The 15× token multiplier of multi-agent systems is a baseline, not a ceiling: a subagent that recursively spawns more subagents, or a tool call that returns an oversized result, can multiply a single query's cost by another 10× or more if the architecture lacks circuit breakers or per-run cost caps.
- **Failure cascades.** A router is itself a single point of decision-making; if its classifier misroutes systematically — for instance, at the decision boundary between "simple" and "complex" queries, which is where routers are most prone to error — the failures can cluster in ways that are harder to detect than a single model's known weaknesses.
- **Shifted governance burden.** Centralizing routing brings compliance and access control into one place, which is a genuine advantage, but it also concentrates responsibility: the gateway becomes the place where privacy, security, and policy enforcement either work correctly for every request or fail for all of them at once.

## Where This Leaves Enterprise AI Strategy

The debate over which single model will "win" was always a poor fit for how enterprises actually consume AI. Agentic workflows have made the economics of single-model deployment untenable, multi-model usage is now the majority pattern among large enterprises, and a genuine vendor ecosystem — spanning academic routers, commercial gateways, and open-weight inference platforms — has emerged to operationalize the split. The organizations pulling ahead are the ones treating model selection as a continuous, per-request engineering decision rather than a one-time procurement choice. The traffic split isn't a temporary phase on the way to consolidation around one winner; it's becoming the permanent architecture of enterprise AI.

---

### Sources

1. Anthropic — ["How we built our multi-agent research system"](https://www.anthropic.com/engineering/multi-agent-research-system)
2. RouteLLM — ["Learning to Route LLMs from Preference Data"](https://arxiv.org/pdf/2406.18665), published as a conference paper at ICLR 2025
3. Menlo Ventures — ["2025: The State of Generative AI in the Enterprise"](https://menlovc.com/perspective/2025-the-state-of-generative-ai-in-the-enterprise/)
4. Menlo Ventures — ["2025 Mid-Year LLM Market Update"](https://menlovc.com/perspective/2025-mid-year-llm-market-update/)
5. a16z — ["How 100 Enterprise CIOs Are Building and Buying Gen AI in 2025"](https://a16z.com/ai-enterprise-2025/)
6. Business Wire — ["Together AI Raises $800 Million at $8.3 Billion Valuation"](https://www.businesswire.com/news/home/20260701243402/en/Together-AI-Raises-$800-Million-at-$8.3-Billion-Valuation-to-Make-Frontier-AI-Accessible-to-All)
7. TechCrunch — ["OpenRouter more than doubles valuation to $1.3B in a year"](https://techcrunch.com/2026/05/26/openrouter-more-than-doubles-valuation-to-1-3b-in-a-year/)
8. Atlassian Engineering Blog — ["Atlassian's AI Gateway: Best in Class Model Garden"](https://www.atlassian.com/blog/atlassian-engineering/ai-gateway-model-garden)
9. Atlassian Community — ["New AI models now available in Rovo Dev"](https://community.atlassian.com/forums/Rovo-for-Software-Teams-Beta/New-AI-models-now-available-in-Rovo-Dev-including-GPT-5-2-Codex/ba-p/3181530)

### A Note on Verification

Every figure above is drawn from a named, checkable primary source (a vendor's own engineering blog, a peer-reviewed conference paper, or a funding announcement corroborated across multiple outlets). Two items are worth flagging for editorial caution before publication:

- The "6–100x" cost-spread range blends two different comparisons — a customer-reported savings figure from Together AI's funding announcement (6–60×) and a separate engineering analysis of frontier-vs-commodity list pricing (~100×). These are not the same measurement and should not be presented as a single continuous statistic without a footnote explaining the distinction.
- Some secondary sources attribute the "37% of enterprises running 5+ models" figure to Menlo Ventures; the original data point traces to a16z's 2025 CIO survey. The article above cites a16z directly to avoid misattribution.
