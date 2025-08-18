# sales_listener.py
import discord
from decimal import Decimal
from query import fetch_recent_sales, fetch_opensea_sales

def _format_price_ron(value):
    """
    Formatea realPrice asumiendo 18 decimales (wei-like).
    """
    try:
        ron = Decimal(str(value)) / Decimal(10**18)
        ron = ron.quantize(Decimal("0.0001"))  # 4 decimales fijos
        return f"{ron} RON"
    except Exception:
        return str(value)

def _format_price_eth(value):
    """
    Formatea precios en ETH (18 decimales).
    """
    try:
        eth = Decimal(str(value)) / Decimal(10**18)
        eth = eth.quantize(Decimal("0.0001"))
        return f"{eth} ETH"
    except Exception:
        return str(value)

async def notify_sale(channel: discord.abc.Messageable, sale: dict, collection_name: str, market: str, contract_address: str = None):
    assets = sale.get("assets", [])
    token = assets[0].get("token") if assets else {}
    typename = token.get("__typename") if token else "unknown"
    token_id = token.get("tokenId1155") if typename == "Erc1155" else token.get("tokenId721") if typename == "Erc721" else sale.get("tokenId", "¿?")
    name = token.get("name") or f"Token #{token_id}"

    # Imagen: primero la de Ronin, si no hay usa la de OpenSea o placeholder
    image = token.get("image") if token else ""
    if not image:
        image = assets[0].get("image_url", "")
    if not image:
        image = "https://via.placeholder.com/256?text=NFT"

    # Precio
    price_str = _format_price_ron(sale.get("realPrice")) if market == "ronin" else _format_price_eth(sale.get("price"))
    buyer = sale.get("matcher", sale.get("buyer", "¿?"))
    seller = sale.get("maker", sale.get("seller", "¿?"))
    tx_hash = sale.get("txHash")
    assets = sale.get("assets", [])
    quantity = 1
    if assets:
        token = assets[0].get("token", {})
        typename = token.get("__typename", "")
    if typename == "Erc1155":
        quantity = int(assets[0].get("quantity", 1))

    # Precio total (realPrice ya viene en WEI o base units)
    if market == "ronin":
        total_price = int(sale.get("realPrice", 0))
        unit_price = total_price // quantity if quantity > 0 else total_price
        price_total_str = _format_price_ron(total_price)   # ejemplo: "55.0000 RON"
        price_unit_str = _format_price_ron(unit_price)     # ejemplo: "0.5500 RON"
    else:
        total_price = int(sale.get("price", 0))
        unit_price = total_price // quantity if quantity > 0 else total_price
        price_total_str = _format_price_eth(total_price)
        price_unit_str = _format_price_eth(unit_price)



    # URL: Transacción en vez de NFT
    if market == "ronin" and tx_hash:
        url = f"https://app.roninchain.com/tx/{tx_hash}"
    elif market == "opensea" and tx_hash:
        url = f"https://etherscan.io/tx/{tx_hash}"
    else:
        url = discord.Embed.Empty

    embed = discord.Embed(
        title=f"Sale in {collection_name} ({market.capitalize()})",
        description=f"**{name}** (ID: `{token_id}`)",
        url=url
    )

    if quantity > 1:
        embed.add_field(name="Sold for", value=f"{quantity} × {price_unit_str} = {price_total_str}", inline=True)
    else:
        embed.add_field(name="Sold for", value=price_total_str, inline=True)

    embed.add_field(name="Quantity", value=str(quantity), inline=True)
    embed.add_field(name="Buyer", value=f"`{buyer}`", inline=False)
    embed.add_field(name="Seller", value=f"`{seller}`", inline=False)

   

    if image:
        embed.set_thumbnail(url=image)

    embed.set_footer(text=f"{market.capitalize()} • Sales notifier")

    await channel.send(embed=embed)


async def check_sales(
    session,
    channel,
    api_url,
    api_key,
    last_timestamp: int,
    collection_name: str,
    contract_or_slug: str,
    fetch_size: int,
    seen_tx_hashes: set,
    market: str = "ronin",
):
    """
    Pide ventas recientes y notifica las nuevas.
    """
    sales = await fetch_recent_sales(session, api_url, api_key, contract_or_slug, size=fetch_size) if market == "ronin" else await fetch_opensea_sales(session, api_url, api_key, contract_or_slug, last_timestamp)
    print(f"[INFO] Revisando {collection_name} en {market} - {len(sales)} ventas encontradas")

    new_sales = []
    for s in sales:
        ts = int(s.get("timestamp", 0))
        tx = s.get("txHash")
        if ts > last_timestamp or (ts == last_timestamp and tx and tx not in seen_tx_hashes):
            new_sales.append(s)

    if not new_sales:
        return last_timestamp

    new_sales.sort(key=lambda x: (int(x.get("timestamp", 0)), x.get("txHash") or ""))
    for s in new_sales:
        await notify_sale(channel, s, collection_name, market, contract_or_slug)
        tx = s.get("txHash")
        if tx:
            seen_tx_hashes.add(tx)
            if len(seen_tx_hashes) > 2000:
                for _ in range(len(seen_tx_hashes) - 1500):
                    seen_tx_hashes.pop()

    return max(int(s.get("timestamp", 0)) for s in new_sales)
