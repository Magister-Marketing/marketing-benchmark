# Ostrel Botanicals: DNS records of the sending domains

Exported from the DNS host on 12 February 2027. Every TXT record at or under each sending domain is listed.

## mail.ostrel.example

| Name | Type | Value |
|---|---|---|
| mail.ostrel.example | TXT | v=spf1 include:spf.sendloop.example -all |
| mail.ostrel.example | TXT | ostrel-site-verification=7Hc2kQ9pX4 |
| sl1._domainkey.mail.ostrel.example | TXT | v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQP4cBiqBhDwwW48yKpcPBIrCJtMiuEwUm88/65NPlbZDAHWsfO6c/1PXcMFc+cRRROPCGpQBXoXWlTBzoY8SdFxP0Ha6JFkpdFEwPnYiQpruPam3uBJi28cHLvXuuqz3aP+nQa6FxmiqzZUxBKjvhdJIDAQAB |
| k1._domainkey.mail.ostrel.example | TXT | v=DKIM1; p= |
| _dmarc.mail.ostrel.example | TXT | v=DMARC1; p=reject; rua=mailto:dmarc@ostrel.example |

## orders.ostrel.example

| Name | Type | Value |
|---|---|---|
| orders.ostrel.example | TXT | v=spf1 include:spf.sendloop.example include:_spf.helpdeskly.example ~all |
| sl1._domainkey.orders.ostrel.example | TXT | v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQGgbZYk7IvNeZGSFH7UX+snoxQlilQasc2DXaEXSadMQVma2oHPWM6jWsEJrWOszpSNatJPxqxY6bi5NwJcOJPfTYneALG5QUvOzsulNAbgYcAVtMBPEtJqJI2WRvLflfG7b4F0Yh9qF59tN750IuDCIDAQAB |
| _dmarc.orders.ostrel.example | TXT | v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc@ostrel.example |

## eu.ostrel.example

| Name | Type | Value |
|---|---|---|
| eu.ostrel.example | TXT | v=spf1 include:spf.sendloop.example -all |
| sl1._domainkey.eu.ostrel.example | TXT | v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQRiMLxa5utc51ZNPA/8kFf+TKM/QtC448dqnbbnyw0d6icWxcNdfC89cEr6VPbEJQJdLSHMmwcnijJBWKAkD5VHoi4mwKqE6hdRH6R6F4JlWq5lWMDqpIsh8z9Cd5L10RCyjFfg8Br3jXnN0lV9nlE6IDAQAB |
| _dmarc.eu.ostrel.example | TXT | v=DMARC1; p=none; sp=quarantine; rua=mailto:dmarc@ostrel.example |
