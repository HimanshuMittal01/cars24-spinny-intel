# Extraction review — all 21 listings

Per-fixture artifacts under `fixtures/<platform>/<listing_id>/`:

- `page.html` — raw snapshot (what was downloaded)
- `url.txt` — source URL
- `captured_at.txt` — capture timestamp (UTC)
- `extracted.json` — raw fields parsed out of the inline JSON in `page.html`
- `normalized.json` — common-schema view used by the scorer

Below is a quick-scan summary of the four scoring fields per listing. `R` = in the 6-listing ranking, `G` = in the 15-listing gold dataset.

## Cars24

| | listing | URL | price | km | year | owners | accident |
|---|---|---|---:|---:|---:|---:|---|
| G | `10006504768` | [link](https://www.cars24.com/buy-used-hyundai-creta-2016-cars-new-delhi-10006504768/) | ₹484,000 | 69,401 | 2016 | 1 | none |
| G | `10013895179` | [link](https://www.cars24.com/buy-used-hyundai-creta-2016-cars-new-delhi-10013895179/) | ₹499,844 | 35,310 | 2016 | 2 | none |
| G | `10018797175` | [link](https://www.cars24.com/buy-used-hyundai-creta-2017-cars-new-delhi-10018797175/) | ₹485,000 | 43,145 | 2017 | 1 | none |
| R | `10041693110` | [link](https://www.cars24.com/buy-used-hyundai-creta-2020-cars-new-delhi-10041693110/) | ₹950,000 | 50,673 | 2020 | 2 | none |
| R | `10076268734` | [link](https://www.cars24.com/buy-used-hyundai-creta-2021-cars-new-delhi-10076268734/) | ₹764,000 | 50,208 | 2021 | 1 | none |
| R | `10096166769` | [link](https://www.cars24.com/buy-used-hyundai-creta-2019-cars-new-delhi-10096166769/) | ₹700,389 | 66,306 | 2019 | 1 | none |
| G | `10126364760` | [link](https://www.cars24.com/buy-used-hyundai-creta-2016-cars-new-delhi-10126364760/) | ₹508,700 | 86,100 | 2016 | 1 | none |
| G | `10142868769` | [link](https://www.cars24.com/buy-used-hyundai-creta-2020-cars-new-delhi-10142868769/) | ₹862,609 | 94,180 | 2020 | 1 | none |
| G | `10182490193` | [link](https://www.cars24.com/buy-used-hyundai-creta-2017-cars-new-delhi-10182490193/) | ₹539,000 | 76,258 | 2017 | 2 | none |
| G | `10526397177` | [link](https://www.cars24.com/buy-used-hyundai-creta-2017-cars-new-delhi-10526397177/) | ₹607,285 | 28,281 | 2017 | 1 | none |
| G | `11403695190` | [link](https://www.cars24.com/buy-used-hyundai-creta-2018-cars-new-delhi-11403695190/) | ₹640,000 | 109,975 | 2018 | 1 | none |

## Spinny

| | listing | URL | price | km | year | owners | accident |
|---|---|---|---:|---:|---:|---:|---|
| G | `26485864` | [link](https://www.spinny.com/buy-used-cars/gurgaon/hyundai/creta/sx-16-petrol-sector-29-2019/26485864/) | ₹641,000 | 61,731 | 2019 | 2 | none |
| G | `26620139` | [link](https://www.spinny.com/buy-used-cars/ghaziabad/hyundai/creta/sx-15-diesel-indirapuram-2022/26620139/) | ₹1,176,001 | 57,299 | 2022 | 1 | none |
| G | `27723929` | [link](https://www.spinny.com/buy-used-cars/gurgaon/hyundai/creta/sx-o-14-turbo-7-dct-sohna-road-2020/27723929/) | ₹1,083,000 | 63,745 | 2020 | 2 | none |
| G | `27767099` | [link](https://www.spinny.com/buy-used-cars/gurgaon/hyundai/creta/sx-15-petrol-sector-29-2022/27767099/) | ₹954,000 | 86,736 | 2022 | 1 | none |
| R | `27839393` | [link](https://www.spinny.com/buy-used-cars/ghaziabad/hyundai/creta/sx-o-14-turbo-7-dct-indirapuram-2020/27839393/) | ₹987,000 | 90,428 | 2020 | 1 | none |
| G | `28185248` | [link](https://www.spinny.com/buy-used-cars/noida/hyundai/creta/sx-15-petrol-2023/28185248/) | ₹1,294,000 | 22,621 | 2023 | 1 | none |
| R | `28198885` | [link](https://www.spinny.com/buy-used-cars/faridabad/hyundai/creta/sx-16-at-petrol-sector-27-2019/28198885/) | ₹747,000 | 88,785 | 2019 | 1 | none |
| G | `28282235` | [link](https://www.spinny.com/buy-used-cars/gurgaon/hyundai/creta/sx-16-petrol-sector-29-2018/28282235/) | ₹638,000 | 100,408 | 2018 | 1 | none |
| R | `28476005` | [link](https://www.spinny.com/buy-used-cars/gurgaon/hyundai/creta/sx-o-15-petrol-cvt-sohna-road-2022/28476005/) | ₹1,347,000 | 33,191 | 2022 | 1 | none |
| G | `28552231` | [link](https://www.spinny.com/buy-used-cars/gurgaon/hyundai/creta/s-plus-15-petrol-knight-sohna-road-2023/28552231/) | ₹1,073,000 | 51,448 | 2023 | 1 | none |

## How to verify a single listing

Open the listing's URL in a browser and compare what's displayed against `fixtures/<platform>/<listing_id>/normalized.json`. The four scoring fields (price, km, year, owners) and the accident flag should match.

`extracted.json` shows the raw key-value dict the extractor pulled from the page's inline JSON — useful if you want to see what other fields the platform exposes (e.g., `lastServicedAt`, `inspection_report`, `pricing.market_price`) beyond what we score on.