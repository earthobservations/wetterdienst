# Met Office

UK Met Office (MIDAS Open)

## Overview

The Met Office provider serves UK land surface observations from the **MIDAS Open** archive
hosted at CEDA (the Centre for Environmental Data Analysis), covering daily and hourly
resolution. A free CEDA account is required.

## License

MIDAS Open is © Crown Copyright, Met Office and published under the
[UK Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/),
which permits copying, adaptation and commercial use with attribution. The
[MIDAS Open dataset catalogue record](https://catalogue.ceda.ac.uk/uuid/dbd451271eb04662beade68da43546e1/)
gives the citation under "Citable as", and its
[ISO record](https://catalogue.ceda.ac.uk/export/xml/gemini2.3/dbd451271eb04662beade68da43546e1.xml) says
"you must cite them correctly using the citation given on the CEDA Data Catalogue record". The
`attribution` of an answer is that citation, without the date of citation.

The files are downloaded from the CEDA Archive with a token that the library mints from your CEDA account, so the
[CEDA Archive Terms and Conditions](https://help.ceda.ac.uk/article/4640-ceda-archive-terms-and-conditions) (version of
25 May 2018, read 2026-11-06) bind the account holder besides the licence. They ask the archive user: "Only to use the
service/resource for the purposes for which you were given access", "Not to use another person's account, nor to let
other people use your accounts, except by agreement with us", "To comply with any special conditions that may apply to
particular resources", and "To inform us if you believe your credentials have been compromised"; CEDA "may suspend your
access ... if it seems to us that you are breaking these Terms and Conditions". They state no rate limit. Whether a
server that answers other people's queries with your token is "letting other people use your account" they do not say:
the people it serves use the server, not the account, which is a reading and not CEDA's. A shared instance should ask
CEDA, see [what it does with the data](../data-use.md#keys-and-credentials). Wetterdienst keeps a file for twelve hours.

```{toctree}
:hidden:

observation/index.md
```
