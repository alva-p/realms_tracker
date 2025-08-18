# query.py
import aiohttp

async def fetch_recent_sales(session, api_url, api_key, contract_address, size=10, from_=0):
    query = """
    query RecentSales($tokenAddress: String!, $from: Int!, $size: Int!) {
      recentlySolds(from: $from, size: $size, tokenAddress: $tokenAddress) {
        results {
          assets {
            token {
              __typename
              ... on Erc1155 {
                tokenId1155: tokenId
                name
                image
              }
              ... on Erc721 {
                tokenId721: tokenId
                name
                image
              }
            }
            quantity
          }
          maker
          matcher
          realPrice
          timestamp
          txHash
        }
      }
    }
    """
    variables = {"tokenAddress": contract_address, "from": from_, "size": size}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key

    async with session.post(api_url, json={"query": query, "variables": variables}, headers=headers) as r:
        if r.status != 200:
            body = await r.text()
            raise RuntimeError(f"GraphQL HTTP {r.status}: {body}")
        data = await r.json()

    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]["recentlySolds"]["results"]

async def fetch_opensea_sales(session, api_url, api_key, slug_or_contract, last_checked):
    headers = {"X-API-KEY": api_key}
    params = {"event_type": "sale", "occurred_after": int(last_checked), "collection_slug": slug_or_contract}
    async with session.get(api_url, headers=headers, params=params) as r:
        if r.status != 200:
            body = await r.text()
            raise RuntimeError(f"OpenSea HTTP {r.status}: {body}")
        data = await r.json()
    return [
        {
            "tokenId": event["nft"]["identifier"],
            "price": float(event["payment"]["quantity"]) / 10**18,
            "maker": event.get("from_account", {}).get("address", "¿?"),
            "matcher": event.get("to_account", {}).get("address", "¿?"),
            "timestamp": event["event_timestamp"],
            "txHash": event.get("transaction_hash", ""),
            "image": event.get("nft", {}).get("image_url")
        } for event in data.get("events", [])
    ]