# Evaluation results

Detection: rules, voice pressure and claude-haiku-5-5
Scams flagged: 5 of 5
Legitimate calls with a false alert: 1 of 4 (1 alerts in total)
Delay from first red flag to first alert: mean 3.0s, worst 8.2s

| Call | Label | Flagged | First red flag (s) | First alert (s) | Delay (s) | Alerts | Reached high | Peak score | Correct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bank_safe_account | scam | yes | 29.664 | 33.9 | 4.2 | 2 | yes | 98.6 | yes |
| crypto_investment | scam | yes | 32.332 | 39.3 | 6.9 | 2 | yes | 97.0 | yes |
| dentist_appointment | legit | no | - | - | - | 0 | no | 3.0 | yes |
| energy_bill_reminder | legit | no | - | - | - | 0 | no | 19.2 | yes |
| hmrc_tax_threat | scam | yes | 21.787 | 28.9 | 7.2 | 2 | yes | 98.7 | yes |
| parcel_redelivery_fee | scam | yes | 25.735 | 34.0 | 8.2 | 2 | yes | 92.0 | yes |
| real_bank_fraud_alert | legit | no | - | - | - | 0 | no | 22.2 | yes |
| surprise_party_friend | legit | yes | - | 32.2 | - | 1 | no | 49.1 | no |
| tech_support_remote_access | scam | yes | 31.961 | 20.5 | -11.5 | 2 | yes | 95.8 | yes |
