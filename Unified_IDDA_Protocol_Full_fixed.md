# Unified Protocol for Iterative Dual Domain Adaptation (IDDA) in Neural Machine Translation

## Introduction and Scope

This protocol describes how ChatGPT (or a similar AI agent) can autonomously perform **Iterative Dual Domain Adaptation (IDDA)** for Neural Machine Translation. IDDA is a multi-step training framework that iteratively transfers translation knowledge between domain-specific NMT models in both directions to maximize in-domain translation quality. A new **synthetic-data bootstrap module** is integrated, enabling the procedure to run even when the user provides no parallel or monolingual data. The method covers three adaptation setups:

* **One-to-One:** a single source domain and a single target domain.
* **Many-to-One:** multiple source domains adapted to one target domain.
* **Many-to-Many:** multiple domains mutually improve each other (multi-domain adaptation).

The goal is to produce a unified, end-to-end executable procedure that covers all scenarios and data conditions. ChatGPT requires only the following per-domain inputs (for each domain involved):

* *Optional:* **In-domain parallel corpus** (aligned source–target sentence pairs).
* *Optional:* **In-domain monolingual text** (in the source language only).
* *Mandatory:* **Domain label + Source Language + Target Language** (names of languages, which ChatGPT will convert to language codes; plus an *optional* desired synthetic pair count).

Using these inputs, the protocol ensures a parallel corpus is available for each domain (either using provided data or by generating synthetic data), and then performs IDDA through iterative knowledge distillation between domain models to adapt them. The outcome is a set of trained domain-specific NMT models with improved translation quality on their respective domains (especially the target domain of interest in one-to-one or many-to-one scenarios).

## Core Definitions and Assumptions

* **Domain-Specific Corpus:** A parallel corpus (source–target sentence pairs) for a given domain. If no real in-domain parallel data is provided, a synthetic parallel corpus will be fabricated automatically in *Pre-Step 0*.
* **Domain-Specific NMT Model:** A transformer-based machine translation model trained on one domain’s parallel corpus (real + any synthetic data).
* **Knowledge Distillation (KD):** Training a student model to match a teacher model’s output distribution while also fitting ground-truth reference data. In this protocol, KD is used during knowledge transfer to prevent catastrophic forgetting of previously learned translation knowledge.
* **Proxy A-Distance:** An empirical distance metric for estimating domain similarity (based on the generalization error of a classifier distinguishing the domains). A smaller proxy A-distance indicates two domains are more similar. This metric will be used to rank or weight domains by similarity.
* **Best Checkpoint (θ\***): The best model checkpoint for a domain (source or target) based on development set performance. The best model θ\*\_s or θ\*\_t serves as a fixed teacher to supervise the opposite domain’s model training until a new better model is found.
* **Iteration Count (K):** Number of full IDDA cycles (each cycle = two knowledge transfers in one-to-one, or a round of multi-directional transfers in other scenarios). Default K = 3 for One-to-One and Many-to-One setups, and K = 4 for Many-to-Many setups. Stop earlier if development set scores plateau (no improvement) before reaching K iterations.

## Pre-Step 0: Synthetic-Data Bootstrapper (Data Preparation)

**Purpose:** Ensure every domain has an initial parallel training corpus. This step is executed **once per domain** *before* the adaptation steps (Step 1 onward). If the user has not provided a parallel corpus for a domain, this module will create a synthetic parallel corpus so that no domain is left without bilingual training data.

**Decision Tree:** For each domain, use the available input to decide among Module A, B, or C:

* **A. Parallel corpus supplied** → *Skip Pre-Step 0* for this domain (use the provided parallel corpus directly).
* **B. Only monolingual in-domain text supplied** → *Run Module B* to convert monolingual data into synthetic parallel data.
* **C. Nothing supplied (except domain label & language pair)** → *Run Module C* to auto-generate a synthetic parallel corpus from scratch.

After this decision, every domain will have at least a synthetic parallel corpus ready for training.

### Module B: Monolingual → Pseudo-Parallel

*Input:* Monolingual in-domain text in the source language (SL).

*Process:* Convert the monolingual corpus into a pseudo-parallel corpus via translation:

1. **Chunk and Clean:** Split the monolingual text into sentence chunks and clean the data (remove overly long sentences, non-text noise, etc.).
2. **Translate to Target:** Translate each source-language sentence into the target language (TL) using ChatGPT (or another high-quality translation engine). This produces a synthetic target sentence for each source sentence.
3. **Filter Noise:** Filter out any sentence pairs that are obviously misaligned or contain low-quality translations (e.g. nonsensical or untranslated output).
4. **(Optional) Back-translate:** Optionally, take the synthetic TL sentences and translate them back into the source language, checking that the back-translation is close to the original source. This can help detect and remove badly translated pairs.
5. **Save Synthetic Corpus:** Pair each original source sentence with its translated target sentence to form a parallel corpus, and save it as a file (e.g. `synthetic_{domain}_{SL}-{TL}.txt`).

The result is a pseudo-parallel corpus for the domain, derived from the provided monolingual data.

### Module C: Zero-Data Author-and-Translate

*Input:* Domain name/description, source language (SL), target language (TL), and a desired sentence pair count **N** (default N = 100 if not specified).

*Process:* Autonomously generate a synthetic parallel corpus by creating in-domain sentences and translating them:

1. For *i = 1* to *N* (the desired number of sentence pairs):

   * **Generate In-Domain Source Sentence:** Use ChatGPT to **author** one plausible sentence in the source language that fits the specified domain. The sentence should be of moderate length (approximately 10–25 words) and representative of the domain's content/style.
   * **Translate to Target:** Immediately translate the generated source sentence into the target language using ChatGPT (or an NMT model, if available). This yields a synthetic target sentence.
   * **Quality Check & Deduplication:** Perform basic noise checks on the pair (e.g. ensure the translation is not identical to the source, verify it is fluent and relevant). Discard or regenerate any pair that is low-quality or a near-duplicate of a previous pair.
2. Save all retained sentence pairs as a synthetic parallel corpus file (e.g. `synthetic_{domain}_{SL}-{TL}.txt`).

This module effectively bootstraps a parallel corpus from zero data by leveraging the generative capabilities of ChatGPT to simulate in-domain content.

**Note:** If real parallel sentence pairs for the domain are available (from the user or other sources), those **real pairs should be given higher weight during training** (e.g. oversample or assign larger loss weight) to offset the noise in synthetic data. The synthetic data is a stop-gap solution to enable training; real human-aligned data, if present, is inherently more reliable and should thus have a stronger influence on the model.

---

With Pre-Step 0 completed for each domain, every domain now has a parallel training corpus (real and/or synthetic). Next, the protocol proceeds to train and adapt domain-specific NMT models using the IDDA framework. Depending on the adaptation scenario (One-to-One, Many-to-One, or Many-to-Many), follow the corresponding sequence of steps below.

## Scenario 1: One-to-One Domain Adaptation

*(Single source domain → single target domain adaptation.)*

**Applicable when:** We have two domains: a source domain and a target domain. The goal is to improve the target domain’s translation model using knowledge from the source domain and vice versa, through iterative dual adaptation. (For example, adapting a generic out-of-domain model and an in-domain model to each other.)

**Step 0: Data Preparation for Both Domains** – Ensure both the **source domain** and **target domain** have parallel corpora ready. Run **Pre-Step 0** for each domain if not already done (per the Decision Tree above). This yields corpus *D<sub>s</sub>* (source-domain parallel data) and *D<sub>t</sub>* (target-domain parallel data), each containing real data if available plus synthetic data as needed.

**Step 1: Initial Training of Domain Models** – Train an NMT model on each domain’s corpus to obtain initial models θ<sub>s</sub><sup>(0)</sup> and θ<sub>t</sub><sup>(0)</sup>. Each model is a transformer trained from scratch (or a pre-trained baseline) on its respective domain data (using the combined real + synthetic parallel corpus). After training:

* Set the *best model* for source domain θ<sub>s</sub><sup>\*</sup> = θ<sub>s</sub><sup>(0)</sup>.
* Set the *best model* for target domain θ<sub>t</sub><sup>\*</sup> = θ<sub>t</sub><sup>(0)</sup>.

These best models (θ<sub>s</sub><sup>*</sup>, θ<sub>t</sub><sup>*</sup>) will serve as initial teachers for knowledge distillation. If any real parallel data was provided, it should have been up-weighted in training to mitigate synthetic noise.

**Step 2: Iterative Bidirectional Knowledge Transfer** – Perform **K** rounds of iterative dual adaptation between the two models (default K = 3, or until dev set performance converges). In each iteration *k* (from 1 to K):

* **2(a) Transfer Source → Target:** Use the current *source-domain model* (θ<sub>s</sub><sup>(k−1)</sup>) to improve the *target-domain model*. Initialize the new target model θ<sub>t</sub><sup>(k)</sup> with the parameters of θ<sub>t</sub><sup>(k−1)</sup> (or θ<sub>t</sub><sup>\*</sup>, optionally) and train it on the target domain data *D<sub>t</sub>*, but with guidance from the source side:

  * **Knowledge Distillation:** During this training, have the *current best target model* θ<sub>t</sub><sup>*</sup> act as a teacher to supervise θ<sub>t</sub><sup>(k)</sup> (preventing it from degrading prior target-domain knowledge). Simultaneously, the source model θ<sub>s</sub><sup>(k−1)</sup> provides new knowledge via its predictions (since θ<sub>t</sub><sup>(k)</sup> was initialized from θ<sub>s</sub><sup>(k−1)</sup>). The training objective combines two goals: (i) fit the target-domain parallel data (minimize translation error on *D<sub>t</sub>*), and (ii) match the output distribution of the teacher θ<sub>t</sub><sup>*</sup> (minimize Kullback–Leibler divergence or other divergence between θ<sub>t</sub><sup>(k)</sup> and θ<sub>t</sub><sup>\*</sup>). A weight coefficient **λ** balances these two terms (λ tuned on dev set or set to a value < 1; if λ = 0, this reduces to plain fine-tuning without knowledge distillation).
  * **Evaluation & Best Model Update:** Evaluate the new target model θ<sub>t</sub><sup>(k)</sup> on the target-domain dev set *D<sub>v,t</sub>*. If its performance exceeds that of the previous best target model θ<sub>t</sub><sup>*</sup>, then update θ<sub>t</sub><sup>*</sup> = θ<sub>t</sub><sup>(k)</sup> (i.e. retain this as the new best checkpoint for target domain). (If it does not improve, θ<sub>t</sub><sup>\*</sup> remains as is, and the current θ<sub>t</sub><sup>(k)</sup> is still used for the next step but not marked “best”.)

* **2(b) Transfer Target → Source:** Next, use the just-updated *target-domain model* (θ<sub>t</sub><sup>(k)</sup>) to improve the *source-domain model*. Initialize a new source model θ<sub>s</sub><sup>(k)</sup> with parameters of θ<sub>s</sub><sup>(k-1)</sup> (or from θ<sub>t</sub><sup>(k)</sup>, since that contains some newly transferred knowledge), and train it on the source domain data *D<sub>s</sub>* with analogous knowledge distillation:

  * **Knowledge Distillation:** Use the *current best source model* θ<sub>s</sub><sup>*</sup> as a teacher to guide θ<sub>s</sub><sup>(k)</sup> during training on *D<sub>s</sub>*. The loss again combines (i) a standard MT loss on the source-domain data and (ii) a distillation loss to keep θ<sub>s</sub><sup>(k)</sup>’s outputs close to those of the teacher θ<sub>s</sub><sup>*</sup>. (In practice, initialize θ<sub>s</sub><sup>(k)</sup> with θ<sub>t</sub><sup>(k)</sup>’s weights to import target-domain knowledge, then fine-tune on source data while using KD to not forget source capability.)
  * **Evaluation & Best Model Update:** Evaluate θ<sub>s</sub><sup>(k)</sup> on the source-domain dev set *D<sub>v,s</sub>*. If its performance is better than the previous best source model θ<sub>s</sub><sup>*</sup>, update θ<sub>s</sub><sup>*</sup> = θ<sub>s</sub><sup>(k)</sup>.

* **2(c) Iterate:** Continue to the next iteration (k+1) unless convergence is reached. In the next iteration, the “previous” models θ<sub>s</sub><sup>(k)</sup> and θ<sub>t</sub><sup>(k)</sup> (from iteration k) become the starting points to transfer knowledge again. Always use the fixed best checkpoints (θ<sub>s</sub><sup>*</sup>, θ<sub>t</sub><sup>*</sup>) as teachers for distillation to ensure no loss of previously attained knowledge. Repeat the two transfer sub-steps for k = 1, 2, ..., K.

**Step 3: Completion** – After K iterations (or earlier if stopped due to no further improvement), the protocol ends. The final adapted **target-domain NMT model** (θ<sub>t</sub><sup>*</sup>) is the primary output of interest, having incorporated knowledge from the source domain while retaining its own in-domain accuracy. The **source-domain model** (θ<sub>s</sub><sup>*</sup>) is also updated, now containing some information gleaned from the target domain (useful if bidirectional translation is needed).

Both models are preserved, but typically the target domain’s improved model is used for deployment on that domain’s translations. All through training, the use of knowledge distillation and best-model teachers helps protect against noise or catastrophic forgetting, and the dev-set evaluations ensure that only improvements are retained at each step (a form of performance gating).

## Scenario 2: Many-to-One Domain Adaptation

*(Multiple source domains → one target domain adaptation.)*

**Applicable when:** There is one target domain we care about, and multiple *source domains* (out-of-domain or auxiliary domains) with available parallel data. We want to leverage all N source-domain corpora to improve a single target-domain NMT model. (For example, adapting a target domain like “Medical” using several other domains like “News”, “Legal”, etc. as sources of additional knowledge.)

**Step 0: Data Preparation for All Domains** – Ensure the **target domain** and each **source domain (1…N)** have parallel corpora. Run **Pre-Step 0** for the target domain and for each source domain that lacks a parallel corpus. After this, we have:

* *D<sub>t</sub>*: target-domain parallel corpus (real + synthetic).
* *D<sub>s<sub>i</sub></sub>* for i = 1…N: each source-domain parallel corpus (real + synthetic).

**Step 1: Initial Training of NMT Models** – Train initial NMT models on each domain’s data:

* For each source domain i (i = 1…N), train a model θ<sub>s\_i</sub><sup>(0)</sup> on *D<sub>s\_i</sub>*.
* Train a target-domain model θ<sub>t</sub><sup>(0)</sup> on *D<sub>t</sub>*.

After this:

* For all i, set θ<sub>s\_i</sub><sup>\*</sup> = θ<sub>s\_i</sub><sup>(0)</sup> (each source’s best model initially its own trained model).
* Set θ<sub>t</sub><sup>\*</sup> = θ<sub>t</sub><sup>(0)</sup> (target’s best model initially).

**Step 2: Domain Similarity Calculation & Source Ordering** – Compute the similarity between each source domain and the target domain, to determine an optimal adaptation sequence:

* **Calculate Proxy A-Distance:** For each source domain *i*, estimate the **domain-level similarity** to the target by computing the proxy A-distance between corpus *D<sub>s\_i</sub>* and *D<sub>t</sub>*. (E.g., train a simple binary classifier to distinguish target vs. source\_i sentences and compute d<sup>̂</sup><sub>A</sub>(i,t) = 2(1 - 2ε), where ε is the classification error rate. A higher ε (i.e. more confusion) implies domains are more similar, yielding a smaller distance.)
* **Rank Sources by Similarity:** Order the source domains by *decreasing similarity* to the target domain (equivalently, in **increasing order of proxy A-distance**). Let the ordered sequence be \[s′<sub>1</sub>, s′<sub>2</sub>, …, s′<sub>N</sub>], where s′<sub>1</sub> is the source domain most similar to the target, and s′<sub>N</sub> the least similar.

Rationale: Transferring the most relevant (closest) domain first helps the target model preserve that domain’s knowledge, since later transfers (from less similar domains) are less likely to override the foundational improvements from the closest domain.

**Step 3: Iterative Sequential Adaptation (K Iterations)** – Adapt the target model using each source domain in turn, in the determined order, for multiple cycles. Perform **K** iterations (default K = 3 for many-to-one):

* For *k = 1* to *K* (iteration loop):

  * For each source domain *s′<sub>i</sub>* in order (i = 1 to N):

    1. **Transfer s′<sub>i</sub> → Target:** Using the current model of source domain s′<sub>i</sub> (θ<sub>s′<sub>i</sub></sub><sup>(k-1)</sup>), transfer its knowledge to the target domain model. Initialize the target model (temporary) from θ<sub>t</sub><sup>(k-1)</sup> and train it on *D<sub>t</sub>* with knowledge distillation: use the current best target model θ<sub>t</sub><sup>*</sup> as a teacher (to retain prior target knowledge) while leveraging θ<sub>s′<sub>i</sub></sub><sup>(k-1)</sup>’s outputs (by initializing or mixing weights). This is similar to Step 2(a) in one-to-one, except the “source” is now one of the many source domains. After training, evaluate θ<sub>t</sub><sup>(k)</sup> on *D<sub>v,t</sub>*; if improved, update θ<sub>t</sub><sup>*</sup>.
    2. **Transfer Target → s′<sub>i</sub>:** Now transfer knowledge back to source domain s′<sub>i</sub>. Initialize a new model θ<sub>s′<sub>i</sub></sub><sup>(k)</sup> from θ<sub>s′<sub>i</sub></sub><sup>(k-1)</sup> (or from the updated θ<sub>t</sub><sup>(k)</sup> to import target knowledge) and train on *D<sub>s′<sub>i</sub></sub>* with KD: the teacher is the best source model θ<sub>s′<sub>i</sub></sub><sup>*</sup>, preserving that domain’s prior ability. After training, evaluate θ<sub>s′<sub>i</sub></sub><sup>(k)</sup> on its dev set; if improved, update θ<sub>s′<sub>i</sub></sub><sup>*</sup>.
    3. **Continue to Next Source:** Proceed to the next source domain s′<sub>i+1</sub> and repeat the two sub-steps, using the updated target model (θ<sub>t</sub><sup>(k)</sup>) as the starting point for each new transfer. Each source domain is sequentially distilled into the target model and then refreshed from the target model in return.
  * End for (all source domains in iteration k).
* End for (iterations 1…K).

Throughout this process, the target-domain model θ<sub>t</sub> is incrementally improved by absorbing knowledge from each source domain one by one, while each source-domain model also gets a chance to learn from the target model. Crucially, by following the similarity-ranked order, the **most similar source domain is integrated first**, and its knowledge is better preserved during later adaptation from more distant domains. Knowledge distillation (with an appropriate λ) is applied in each transfer to retain previously learned content. The dev-set evaluations ensure that the best models θ<sub>t</sub><sup>*</sup> and θ<sub>s\_i</sub><sup>*</sup> are updated only when improvements occur, protecting against regression.

**Step 4: Completion** – After K full cycles, or when the target-domain dev set score plateaus, conclude the adaptation. The final **target-domain NMT model** θ<sub>t</sub><sup>*</sup> is the output, having successfully incorporated translation knowledge from all N source domains. This model should outperform the initial θ<sub>t</sub><sup>(0)</sup> on in-domain translation quality. Additionally, each source domain’s model θ<sub>s\_i</sub><sup>*</sup> has been updated (often marginally improving on its original quality or at least preserved via the knowledge exchange).

The many-to-one procedure thus produces an enhanced target model, aided by multiple sources, while mitigating catastrophic forgetting by iterative two-way KD and careful ordering.

*(Note: In practice, one could fine-tune the transfer schedule: for instance, the number of iterations K or passes per source might be adjusted, and if some source domains are very dissimilar, their influence could be reduced. The above method inherently does this by ordering; one could also limit λ or training epochs for far domains to prevent noise.)*

## Scenario 3: Many-to-Many Domain Adaptation

*(Multiple domains → mutual multi-domain adaptation.)*

**Applicable when:** There are N domains, each with its own parallel corpus and initial NMT model, and we want all domain-specific models to improve by exchanging knowledge with each other. This scenario generalizes the adaptation process to a network of domains, where every domain’s model can learn from every other domain’s model. For example, domains could be different topical domains (News, Legal, Spoken, Thesis, etc.), and we aim to enhance all domain models simultaneously through iterative knowledge transfer.

**Step 0: Data Preparation for All Domains** – Ensure **all N domains** have parallel corpora available. Run **Pre-Step 0** for each domain lacking a corpus. We obtain corpora *D<sub>1</sub>, D<sub>2</sub>, ..., D<sub>N</sub>* for the N domains.

**Step 1: Initial Training of Domain Models** – Train an NMT model on each domain’s corpus to get initial models θ<sub>1</sub><sup>(0)</sup>, θ<sub>2</sub><sup>(0)</sup>, ..., θ<sub>N</sub><sup>(0)</sup>. After this initial training:

* For each domain *i*, set θ<sub>i</sub><sup>\*</sup> = θ<sub>i</sub><sup>(0)</sup> as the best model for that domain.
* All domain models start with only their own knowledge.

**Step 2: Compute Domain Similarities (all pairs)** – (Optional but recommended) Calculate pairwise domain similarity measures to guide knowledge transfer weighting:

* For each pair of domains (i, j), compute a similarity score or distance (e.g., proxy A-distance d<sub>A</sub>(i,j)). This results in a matrix of domain similarities. This will be used to weight the influence of each domain on others during multi-domain knowledge transfer.
* Alternatively, heuristic similarities can be used (if formal calculation is not feasible for ChatGPT, it can qualitatively assess which domains are more related based on their descriptions or sample texts).

**Step 3: Iterative Multi-Domain Knowledge Exchange (K Iterations)** – Perform **K** iterations of mutual knowledge distillation among all domain models (default K = 4 for many-to-many, or stop early if no further improvements):

* For *k = 1* to *K*:

  * For each domain *i* (i = 1…N):

    1. **Multi-Teacher Knowledge Distillation:** Construct an intermediate model φ<sub>i</sub><sup>(k)</sup> for domain *i* by leveraging *all other domains’ models* {θ<sub>j</sub><sup>(k-1)</sup> for j ≠ i} as teachers. Train φ<sub>i</sub><sup>(k)</sup> on the union of all other domains’ data {D<sub>j</sub> : j ≠ i}, using knowledge distillation from each teacher model θ<sub>j</sub><sup>(k-1)</sup>:

       * Each domain *j ≠ i* provides a teacher model and its data D<sub>j</sub>. As φ<sub>i</sub><sup>(k)</sup> is trained on D<sub>j</sub>, encourage its outputs to match the teacher θ<sub>j</sub><sup>(k-1)</sup>’s outputs (this can be done by minimizing cross-entropy with the teacher’s predicted probability distribution, or an L2 loss on output logits).
       * **Similarity-Weighted Influence:** Apply weights to each teacher’s loss contribution based on domain similarity — i.e. if domain *j* is very similar to domain *i*, its knowledge is given a higher weight in training φ<sub>i</sub><sup>(k)</sup>, whereas a more distant domain’s influence is down-weighted. This ensures φ<sub>i</sub> focuses on domain-common knowledge that is most relevant to domain *i*.
       * The outcome is φ<sub>i</sub><sup>(k)</sup>, a *multi-domain distilled model* that has absorbed translation knowledge from all other domains (as of iteration k-1).
    2. **Initialize Domain-i Model:** Initialize a new model θ<sub>i</sub><sup>(k)</sup> (candidate for iteration k) with the parameters of φ<sub>i</sub><sup>(k)</sup>. Now φ<sub>i</sub><sup>(k)→</sup>θ<sub>i</sub><sup>(k)</sup>, meaning domain i’s model starts off containing the merged knowledge from other domains.
    3. **Self-Distillation Fine-Tuning:** Fine-tune θ<sub>i</sub><sup>(k)</sup> on domain *i*’s own data D<sub>i</sub> to restore and reinforce domain-specific translation ability. During this fine-tuning, use knowledge distillation with domain i’s previous best model θ<sub>i</sub><sup>\*</sup> (or θ<sub>i</sub><sup>(k-1)</sup>) as the teacher. This step ensures the model does not stray from accuracy on in-domain data while it incorporates outside knowledge:

       * The training loss here has two components: (i) a standard MT loss on D<sub>i</sub> (to fit the reference translations in the in-domain corpus), and (ii) a **prediction divergence loss** that penalizes the new model if its outputs deviate from the previous model on the same input. The second term effectively preserves the original domain proficiency (self-distillation), preventing the multi-domain knowledge from harming in-domain performance.
       * A weighting parameter **λ<sub>ds</sub>** controls the balance: e.g., λ<sub>ds</sub> = 1 means full teacher guidance (no change in outputs from previous model), λ<sub>ds</sub> = 0 means pure fine-tuning. In practice, λ<sub>ds</sub> can be set initially high and then decreased as training progresses, or over successive iterations.
    4. **Evaluation & Best Model Update:** Evaluate the fine-tuned model θ<sub>i</sub><sup>(k)</sup> on domain i’s dev set *D<sub>v,i</sub>*.

       * If its performance is **better** than the prior best θ<sub>i</sub><sup>*</sup>, then update θ<sub>i</sub><sup>*</sup> = θ<sub>i</sub><sup>(k)</sup> (domain i’s new best model).
       * If its performance is **worse or no better**, one may **revert** to the previous model: e.g., discard θ<sub>i</sub><sup>(k)</sup> and retain θ<sub>i</sub><sup>\*</sup> as the iteration k model. (This is a safeguard to prevent quality degradation – the protocol only keeps improvements. In practice, the algorithm sets θ<sub>i</sub><sup>(k+1)</sup> = θ<sub>i</sub><sup>(k)</sup> only if the new one is better.)
  * End for (each domain i).
  * *(At the end of iteration k, each domain model has potentially been updated once. Now proceed to the next iteration k+1, using the updated models as starting points for the next round of mutual distillation.)*
* End for (iterations 1…K).

During these iterations, two key techniques ensure effective knowledge sharing without forgetting:

* **Multi-Teacher KD (Stage 3.1):** Each domain model is exposed to every other domain’s knowledge through teachers. The use of similarity-based weighting (and a tuning parameter λ<sub>md</sub>) allows the model to gradually integrate common knowledge from others. At early stages, a higher λ<sub>md</sub> (close to 1) can be used so that φ<sub>i</sub> heavily mimics the other models (capturing inter-domain shared patterns), and over time λ<sub>md</sub> can be reduced towards 0, so the influence of teachers lessens and the model relies more on actual data. This schedule (λ<sub>md>: 1 → 0) means initially the model learns to match peers, and later it refines its own knowledge to surpass them.
* **Self-Distillation (Stage 3.3):** By always referencing the domain’s own previous model as a teacher during fine-tuning, we ensure the domain-specific knowledge is not overwritten. The loss term enforcing consistency with the old model’s predictions (weighted by λ<sub>ds</sub>) serves to retain strengths of the old model while the new model is learning from data. Like λ<sub>md</sub>, λ<sub>ds</sub> can be annealed from 1 to 0 over the course of training or iterations, gradually shifting from teacher-forced stability to allowing more change as the model improves.

**Step 4: Completion** – After K iterations of mutual adaptation, the process stops (or earlier if all domains’ dev performance converge and no further improvement is seen). The outcome is a set of **N improved domain-specific NMT models** { θ<sub>1</sub><sup>*</sup>, θ<sub>2</sub><sup>*</sup>, ..., θ<sub>N</sub><sup>\*</sup> }, one for each domain. Each model has **absorbed useful translation knowledge from all other domains** while maintaining (or improving) its performance on its own domain. All models should outperform or equal their initial versions, and importantly, each has gained from domain-common patterns learned via the others. This many-to-many framework can be especially powerful when domains are related (some more than others), as they reinforce each other through the shared training signal.

Each domain’s best model θ<sub>i</sub><sup>\*</sup> can be used for translating text in that domain. Optionally, one could combine all domain models into a single multi-domain model, but the IDDA framework as described keeps them separate, simply improving each with knowledge from the rest.

## Final Considerations

* **Zero-Data Feasibility:** The synthetic data bootstrapper (Pre-Step 0) enables IDDA to run even if the user supplies no in-domain bilingual data at all. This makes the approach broadly applicable, though the quality of synthetic data may affect final performance.
* **Real vs. Synthetic Data Quality:** The translation quality achieved will scale with the amount and quality of parallel data. Synthetic sentence pairs are only a stop-gap solution, not a replacement for real human-translated text. Whenever real parallel data is available, it should be leveraged preferentially. In training, give higher weight to real pairs or mix them in larger proportion, to counteract the noise and inaccuracies in synthetic corpora.
* **Noise Mitigation:** Knowledge distillation and dev-set gating act as safeguards against noise introduction. By always learning from a teacher (the best model so far), each new model is prevented from straying too far or overfitting to noise. Additionally, the rule of only updating the “best” model when a new model outperforms it (and reverting/ignoring if not) ensures that quality never declines from one iteration to the next. These measures help stabilize training, especially when using synthetic or out-of-domain data.
* **Iteration Stop Criteria:** Stop the iterative adaptation after **K** iterations (the default K given for the scenario) **or** when development set scores **plateau** (i.e. no significant improvement over an iteration). In practice, monitor each domain’s dev set; if all domains fail to improve in an iteration, it’s a sign to stop early. Excessive iterations may yield diminishing returns or risk overfitting.
* **Maintaining Original IDDA Logic:** Apart from the addition of the Pre-Step 0 synthetic data bootstrap, all core IDDA procedures remain as in the original framework. The teacher update strategy, similarity-based weighting, iterative bidirectional transfer, and performance gating are unchanged from the method’s foundational design. This unified protocol simply brings all components together, ensuring a single, coherent process that covers data-sparse and data-rich situations alike.

By following this unified protocol, ChatGPT (or an autonomous system) can orchestrate the entire NMT domain adaptation process end-to-end – from data creation (if needed) to iterative model training – with minimal human intervention. The result is a robust adaptation workflow that can handle one-to-one, many-to-one, and many-to-many domain adaptation scenarios in a consistent framework, yielding high-quality domain-specific translation models.