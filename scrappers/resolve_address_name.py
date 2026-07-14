import asyncio
import sys
from urllib.parse import urlencode, quote
from flowster.stdlib.ai.llm import chat
from flowster import FlowSheet, FlowProfile
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

async def resolve_owner_name(address: str) -> str | None:
    address = address.replace(' ', '%20')

    result = await lookup(address)
    result_js = json.loads(result)
    if len(result_js['items']) == 0:
        return None

    raw_name = result_js["items"][0].get("fields", {}).get("Owner")
    if not raw_name:
        return None

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

    result = await chat(
        flow_sheet,
        raw_name,
        system="""Return the name in the format: Last, First.
If there are multiple owners, return the first one only.
If no owner is found, return the original prompt.
Only return the name, do not include any other text or explanation.
""",
    )
    if result.is_err():
        raise RuntimeError(result.err_value)

    return result.ok_value


async def main() -> None:
    if len(sys.argv) < 2:
        print("⚠️  Please supply an address: e.g., `python 1_resolve_address_name.py 2045 W Camus Dr`")
        sys.exit(1)

    address = "%20".join(sys.argv[1:])
    name = await resolve_owner_name(address)
    if name is None:
        print(f"⚠️  No owner found for address: {address}")
        sys.exit(1)

    print(name)

if __name__ == "__main__":
    asyncio.run(main())
