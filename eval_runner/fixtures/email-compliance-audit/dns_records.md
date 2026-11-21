# Ostrel Botanicals: DNS records of the sending domains

Exported from the DNS host on 12 February 2027. Every TXT record at or under each sending domain is listed.

## mail.ostrel.example

| Name | Type | Value |
|---|---|---|
| mail.ostrel.example | TXT | v=spf1 include:spf.sendloop.example -all |
| mail.ostrel.example | TXT | ostrel-site-verification=7Hc2kQ9pX4 |
| sl1._domainkey.mail.ostrel.example | TXT | v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQgzh9aCyBBGmnm+P9Sz6SeB4ZuN2SBREaBRcBhKeuIDAQAB |
| k1._domainkey.mail.ostrel.example | TXT | v=DKIM1; p= |
| _dmarc.mail.ostrel.example | TXT | v=DMARC1; p=reject; rua=mailto:dmarc@ostrel.example |

## orders.ostrel.example

| Name | Type | Value |
|---|---|---|
| orders.ostrel.example | TXT | v=spf1 include:spf.sendloop.example include:_spf.helpdeskly.example ~all |
| sl1._domainkey.orders.ostrel.example | TXT | v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDiXoFWiMUmr64pYvokNx7nOh1C9XsY/bkK58TSixIDAQAB |
| _dmarc.orders.ostrel.example | TXT | v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc@ostrel.example |

## uk.ostrel.example

| Name | Type | Value |
|---|---|---|
| uk.ostrel.example | TXT | v=spf1 include:spf.sendloop.example -all |
| sl1._domainkey.uk.ostrel.example | TXT | v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQY2cSMXbl6oOjxVieVJBs9sydJa/GMWK5gs5weCNXIDAQAB |
| _dmarc.uk.ostrel.example | TXT | v=DMARC1; p=quarantine; pct=25; rua=mailto:dmarc@ostrel.example |

## ca.ostrel.example

| Name | Type | Value |
|---|---|---|
| ca.ostrel.example | TXT | v=spf1 include:spf.sendloop.example -all |
| sl1._domainkey.ca.ostrel.example | TXT | v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQHll1noOBX+bXIZ1kW5/SzZ3LZ9hkZodKRoIBMr9sIDAQAB |
| _dmarc.ca.ostrel.example | TXT | v=DMARC1; p=reject; sp=none; rua=mailto:dmarc@ostrel.example |

## eu.ostrel.example

| Name | Type | Value |
|---|---|---|
| eu.ostrel.example | TXT | v=spf1 include:spf.sendloop.example -all |
| sl1._domainkey.eu.ostrel.example | TXT | v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQaJ3bNoqcUZmXVOxw8BcLBtVH08TnVU/TacTs5JMaIDAQAB |
| _dmarc.eu.ostrel.example | TXT | v=DMARC1; p=none; sp=quarantine; rua=mailto:dmarc@ostrel.example |

## news.ostrel.example

| Name | Type | Value |
|---|---|---|
| news.ostrel.example | TXT | v=spf1 include:spf.sendloop.example -all |
| sl1._domainkey.news.ostrel.example | TXT | v=DKIM1; p= |
| sl2._domainkey.news.ostrel.example | TXT | v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQos2coV0pfcIl7yWQdwkgY5OYkrVJeDqnOXgVxvzwIDAQAB |
| _dmarc.news.ostrel.example | TXT | v=DMARC1; p=reject; rua=mailto:dmarc@ostrel.example |

## promo.ostrel.example

| Name | Type | Value |
|---|---|---|
| promo.ostrel.example | TXT | v=spf1 include:spf.sendloop.example -all |
| promo.ostrel.example | TXT | v=spf1 include:mx.oldesp.example ~all |
| sl1._domainkey.promo.ostrel.example | TXT | v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQhSEzYGENMaJYeokRzfV7saRWBAM4A7Y/8ABfi0pDIDAQAB |
| _dmarc.promo.ostrel.example | TXT | v=DMARC1; p=quarantine; rua=mailto:dmarc@ostrel.example |
