# Evaluation results

Detection: rules and voice pressure only
Scams flagged: 5 of 5
Legitimate calls with a false alert: 1 of 4 (2 alerts in total)
Delay from first red flag to first alert: mean 10.8s, worst 19.8s

| Call | Label | Flagged | First red flag (s) | First alert (s) | Delay (s) | Alerts | Reached high | Peak score | Correct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bank_safe_account | scam | yes | 29.664 | 36.1 | 6.5 | 2 | yes | 99.9 | yes |
| crypto_investment | scam | yes | 32.332 | 42.5 | 10.2 | 2 | yes | 97.0 | yes |
| dentist_appointment | legit | no | - | - | - | 0 | no | 3.0 | yes |
| energy_bill_reminder | legit | no | - | - | - | 0 | no | 27.7 | yes |
| hmrc_tax_threat | scam | yes | 21.787 | 41.6 | 19.8 | 2 | yes | 99.1 | yes |
| parcel_redelivery_fee | scam | yes | 25.735 | 36.8 | 11.1 | 2 | yes | 97.7 | yes |
| real_bank_fraud_alert | legit | no | - | - | - | 0 | no | 3.0 | yes |
| surprise_party_friend | legit | yes | - | 30.0 | - | 2 | yes | 97.9 | no |
| tech_support_remote_access | scam | yes | 31.961 | 38.6 | 6.6 | 2 | yes | 91.7 | yes |
