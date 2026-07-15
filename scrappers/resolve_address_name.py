import asyncio
import sys
from urllib.parse import urlencode, quote
from flowster.stdlib.ai.llm import chat
from flowster import FlowSheet, FlowProfile
from result import Result, Ok, Err
import json

import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.117 Safari/537.36",
    "Accept": "application/json,text/plain, */*;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

async def fetch_cookie(client: httpx.AsyncClient, address: str) -> str:
    search_url = "https://id-kootenai.publicaccessnow.com/Assessor/PropertySearch.aspx"
    params = {
        "s": address,
        "pg": 1,
        "g": -1,
        "moduleId": 470
    }
    full_params = urlencode(params, quote_via=quote)
    resp = await client.get(f"{search_url}?{full_params}", headers=HEADERS)
    resp.raise_for_status()
    cookies = {}
    for raw in resp.headers.get_list("set-cookie"):
        name_value = raw.split(';')[0].strip()
        name, _, value = name_value.partition('=')
        cookies[name.strip()] = value.strip()
    return '; '.join(f"{k}={v}" for k, v in cookies.items())

async def get_data(client: httpx.AsyncClient, address: str, cookie: str) -> str:
    base_url = "https://id-kootenai.publicaccessnow.com/DesktopModules/QuickSearch/API/Module/GetData"
    params = {"keywords": address, "page": 1, "_m": 470}
    headers = {
        **HEADERS,
        "Cookie": cookie,
        "Referer": "https://id-kootenai.publicaccessnow.com/Assessor/PropertySearch.aspx?s={}&pg=1&g=-1&moduleId=470".format(quote(address)),
        "Moduleid": "470",
        "Priority": "u=1, i",
        "Tabid": "38"
    }
    full_params = '&'.join(f"{k}={str(v)}" for k, v in params.items())
    print(f"{base_url}?{full_params}")
    resp = await client.get(f"{base_url}?{full_params}", headers=headers)
    resp.raise_for_status()
    return resp.text

async def lookup(address: str) -> str:
    async with httpx.AsyncClient() as client:
        cookie_str = await fetch_cookie(client, address)
        return await get_data(client, address, cookie_str)

async def resolve_owner_name(flow_sheet: FlowSheet, address: str) -> Result[str, str]:
    address = address.replace(' ', '%20')

    try:
        result = await lookup(address)
    except httpx.HTTPStatusError as e:
        return Err(f"HTTP error {e.response.status_code}: {e}")
    except httpx.HTTPError as e:
        return Err(f"Request error: {e}")

    try:
        result_js = json.loads(result)
    except json.JSONDecodeError as e:
        return Err(f"Invalid response for address {address}: {e}")

    if len(result_js.get('items', [])) == 0:
        return Err(f"No owner found for address: {address}")

    raw_name = result_js["items"][0].get("fields", {}).get("Owner")
    if not raw_name:
        return Err(f"No owner found for address: {address}")

    result = await chat(
            flow_sheet,
            raw_name,
            system="""Return the name in the format: Last, First.
If there are multiple owners, return the first one only.
If no owner is found, return the original prompt.
Only return the name, do not include any other text or explanation.
""",
            credentials='process',
        )
    if result.is_err() or not result.ok_value:
        return Ok(raw_name)

    return result


async def main() -> None:
    if len(sys.argv) < 2:
        print("⚠️  Please supply an address: e.g., `python 1_resolve_address_name.py 2045 W Camus Dr`")
        sys.exit(1)

    profile = FlowProfile({
        'llm': {
            'default': {
                'type': 'ollama',
                #'model_name': 'dolphin-gpu',
                'model_name': 'gpt-oss-gpu-large',
                'streaming': True,
            }
        }
    })
    flow_sheet = FlowSheet( "Dogs", None, profile )

    address = "%20".join(sys.argv[1:])
    result = await resolve_owner_name(flow_sheet, address)
    if result.is_err():
        print(f"⚠️  {result.err_value}")
        sys.exit(1)

    print(result.ok_value)

if __name__ == "__main__":
    asyncio.run(main())
