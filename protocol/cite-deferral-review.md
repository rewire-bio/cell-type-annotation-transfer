# Review of the proposed CITE deferral

**Validity.** The main question is answered by whole-study holdout against author labels (`protocol.md` §1, §6). The protein check was pre-registered as a secondary, descriptive "coarse orthogonal check, not ground truth" (§1, §7). The original plan already allowed scoring to go ahead if the CITE build failed (resume-plan §3, R4). No threshold, K, feature or primary metric depends on the 10x files. **The restriction does not undermine the main question.**

**What is lost.** The reference standard can no longer be checked independently. Author labels may themselves have been made by label transfer, which could favour methods that resemble the authors' pipeline. This bias cannot be bounded without protein data. It must be stated as a limitation, and accuracy must not be described as "validated".

**Blocking conditions** (must hold for the amendment to be acceptable):
- B1. The amendment is approved by the user and hashed **before R6**. If any test scoring happened first, the deferral counts as a post-hoc deviation and must be logged as one.
- B2. Only the gates listed in item 2 change. A diff of `tolerances.json` against the approved hash must show no other edits.
- B3. Test study `a199ca73…` (JDM) is kept. Dropping it with the 10x files would change the primary data.
- B4. The outcome label is "not run", never "pass". The disclosure appears in both the paper and the blog.
- B5. No retries or alternative sources (mirrors, GEO, other CITE datasets, changed headers) without new authorisation.

**Minor.** The blocker comes from a single request. Files 2–4 are unverified, not "failed", and should be described that way.

**Recommendation.** Approve the deferral, subject to B1–B5. Waiting gives nothing for the primary question. Its only benefit would be the secondary check, and that depends on access the user has not authorised. The final decision belongs to the user.
