# End-to-end scenarios

TODO(Hadi): implement each as an automated test.

| # | Scenario | Setup | Expected behaviour |
|---|---|---|---|
| 1 | Happy path | Seed person `0000042101002` | Verified, decision stored with rule version, payment still needs officer approval, audit entries for every step |
| 2 | Misspelled name | Claim as "Mohammad Aslam" vs record "Muhammad Aslam" | Match with variant, lower confidence noted; wrong/uncertain match -> `send_to_human`, never silent approve |
| 3 | Identity service down | `POST /chaos {"error_500": true}` | Case `with_officer` with notes; user sees a calm message, no 500 |
| 4 | Consent withdrawn | Withdraw `payments` consent mid-flow | No ledger call afterwards; audit shows withdrawal; user asked again |
| 5 | Rule changed mid-claim | Admin publishes new rule version during a claim | Old decision keeps its version; new decisions use the new one; both visible in audit |
