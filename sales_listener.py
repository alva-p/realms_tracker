# sales_listener.py
import os
import discord
from decimal import Decimal, getcontext
from query import fetch_recent_sales, fetch_opensea_sales

getcontext().prec = 50  # precisión alta para conversiones

# --- ERC1155 event topic hashes ---
TRANSFER_SINGLE_TOPIC = "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62"
TRANSFER_BATCH_TOPIC  = "0x4a39dc06d4c0dbc64b70af90fd698a233a518aa5d07e595d983b8c0526c8f7fb"

def _format_price_ron(value):
    """Convierte base units (wei de RON) -> 'X.YYYY RON'."""
    try:
        ron = Decimal(str(value)) / Decimal(10**18)
        ron = ron.quantize(Decimal("0.0001"))
        return f"{ron} RON"
    except Exception:
        return str(value)

def _format_price_eth_from_any(value):
    """
    Formatea ETH viniendo en wei (entero grande) o en ETH decimal.
    """
    try:
        s = str(value).strip()
        if s.isdigit():
            wei = Decimal(s)
            if wei >= Decimal(10**12):
                eth = wei / Decimal(10**18)
            else:
                eth = Decimal(s)
        else:
            eth = Decimal(s)
        eth = eth.quantize(Decimal("0.0001"))
        return f"{eth} ETH"
    except Exception:
        return str(value)

def _to_int(x, default=0):
    try:
        s = str(x).strip()
        return int(s) if s else default
    except Exception:
        return default

def _topic_addr_to_checksum(topic_hex: str) -> str:
    """topics[1..3] son direcciones padded a 32 bytes. Tomamos los últimos 20 bytes."""
    if not topic_hex or not topic_hex.startswith("0x"):
        return ""
    h = topic_hex[2:].lower()
    if len(h) < 40:
        return ""
    return "0x" + h[-40:]

def _hexword_to_int(h: str) -> int:
    return int(h, 16)

def _read_uint256_at(data_bytes: bytes, offset: int) -> int:
    return int.from_bytes(data_bytes[offset:offset+32], byteorder="big")

def _read_uint256_array(data_bytes: bytes, offset: int) -> list:
    """
    Decodifica un array dinámico de uint256 según ABI:
    [ length (32b) ][ elem0 (32b) ][ elem1 (32b) ] ...
    offset es relativo al inicio de data.
    """
    length = _read_uint256_at(data_bytes, offset)
    out = []
    pos = offset + 32
    for _ in range(length):
        out.append(_read_uint256_at(data_bytes, pos))
        pos += 32
    return out

async def _rpc_call(session, method: str, params: list, rpc_url: str):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    async with session.post(rpc_url, json=payload, timeout=20) as resp:
        resp.raise_for_status()
        return await resp.json()

async def _erc1155_quantity_from_receipt(session, tx_hash: str, contract_address: str, to_addr_maybe: str = None) -> int:
    """
    Lee el receipt del tx y suma las cantidades transferidas (value) de eventos
    ERC1155 TransferSingle/TransferBatch emitidos por 'contract_address'.
    Si 'to_addr_maybe' se provee, filtra solo logs cuyo 'to' == to_addr_maybe.
    """
    if not tx_hash or not contract_address:
        return 0

    rpc_url = os.getenv("RONIN_RPC_URL", "https://api.roninchain.com/rpc").strip()
    try:
        data = await _rpc_call(session, "eth_getTransactionReceipt", [tx_hash], rpc_url)
        receipt = data.get("result") or {}
        logs = receipt.get("logs") or []
    except Exception:
        return 0

    contract_lc = contract_address.lower()
    to_lc = (to_addr_maybe or "").lower()
    qty_sum = 0

    for lg in logs:
        addr = (lg.get("address") or "").lower()
        if addr != contract_lc:
            continue
        topics = lg.get("topics") or []
        if not topics:
            continue
        t0 = topics[0].lower()

        # TransferSingle(operator, from, to, id, value)
        if t0 == TRANSFER_SINGLE_TOPIC.lower():
            to_topic = topics[3] if len(topics) > 3 else ""
            to_addr = _topic_addr_to_checksum(to_topic).lower()
            if to_lc and to_addr != to_lc:
                continue
            data_hex = (lg.get("data") or "0x")[2:]
            # data = id(32) + value(32)
            if len(data_hex) >= 64 * 2:
                value_hex = data_hex[-64:]
                qty_sum += _hexword_to_int(value_hex)

        # TransferBatch(operator, from, to, ids[], values[])
        elif t0 == TRANSFER_BATCH_TOPIC.lower():
            to_topic = topics[3] if len(topics) > 3 else ""
            to_addr = _topic_addr_to_checksum(to_topic).lower()
            if to_lc and to_addr != to_lc:
                continue
            data_hex = (lg.get("data") or "0x")[2:]
            try:
                data_bytes = bytes.fromhex(data_hex)
                if len(data_bytes) >= 64:
                    ids_off = _read_uint256_at(data_bytes, 0)
                    vals_off = _read_uint256_at(data_bytes, 32)
                    values = _read_uint256_array(data_bytes, vals_off)
                    qty_sum += sum(values)
            except Exception:
                pass

    return qty_sum

async def notify_sale(
    session,  # <-- usamos session para llamar al RPC cuando sea ERC1155
    channel: discord.abc.Messageable,
    sale: dict,
    collection_name: str,
    market: str,
    contract_address: str = None
):
    # --- Datos base ---
    assets = sale.get("assets", []) or []
    token = assets[0].get("token") if assets else {}
    typename = token.get("__typename") if token else "unknown"

    token_id = (
        token.get("tokenId1155") if typename == "Erc1155"
        else token.get("tokenId721") if typename == "Erc721"
        else sale.get("tokenId", "¿?")
    )
    name = token.get("name") or f"Token #{token_id}"

    # Imagen
    image = token.get("image") if token else ""
    if not image and assets:
        image = assets[0].get("image_url", "") or assets[0].get("image", "")
    if not image and market == "opensea":
        image = sale.get("image", "") or image
    if not image:
        image = "https://via.placeholder.com/256?text=NFT"

    # Buyer/Seller/Tx
    buyer = sale.get("matcher", sale.get("buyer", "¿?"))
    seller = sale.get("maker",  sale.get("seller", "¿?"))
    tx_hash = sale.get("txHash")

    # --- Precio TOTAL y Quantity por tipo ---
    sold_value_str = "—"
    show_quantity = False
    quantity_value = None

    if market == "ronin":
        total_wei = _to_int(sale.get("realPrice"))
        price_total_str = _format_price_ron(total_wei)

        if typename == "Erc1155" or "ticket" in (collection_name or "").lower():
            # Tickets (ERC1155): cantidad real desde logs del tx (no usamos assets[].quantity)
            qty = await _erc1155_quantity_from_receipt(session, tx_hash, contract_address or "", to_addr_maybe=buyer)
            if qty > 0:
                quantity_value = qty
                show_quantity = True
            # Siempre mostrar TOTAL
            sold_value_str = price_total_str
        else:
            # ERC721: sin quantity
            sold_value_str = price_total_str

    else:
        # OpenSea: mostrar TOTAL. (Tu fetch_opensea_sales devuelve 'price' en ETH decimal)
        price_total_str = _format_price_eth_from_any(sale.get("price", 0))
        sold_value_str = price_total_str
        # Quantity: la ocultamos por defecto para ERC721; en 1155 solo si tu fetch trae cantidad fiable.

    # --- URL de transacción ---
    if market == "ronin" and tx_hash:
        url = f"https://app.roninchain.com/tx/{tx_hash}"
    elif market == "opensea" and tx_hash:
        url = f"https://etherscan.io/tx/{tx_hash}"
    else:
        url = discord.Embed.Empty

    # --- Embed ---
    embed = discord.Embed(
        title=f"Sale in {collection_name} ({market.capitalize()})",
        description=f"**{name}** (ID: `{token_id}`)",
        url=url
    )

    # Sold for (siempre TOTAL)
    embed.add_field(name="Sold for", value=sold_value_str, inline=True)

    # Quantity (solo tickets ERC1155 de Ronin, desde logs del tx)
    if show_quantity and quantity_value is not None:
        embed.add_field(name="Quantity", value=str(quantity_value), inline=True)

    # Buyer / Seller
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
    """Pide ventas recientes y notifica las nuevas."""
    sales = (
        await fetch_recent_sales(session, api_url, api_key, contract_or_slug, size=fetch_size)
        if market == "ronin"
        else await fetch_opensea_sales(session, api_url, api_key, contract_or_slug, last_timestamp)
    )
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
        # ⬇ pasamos session a notify_sale para poder leer el receipt cuando sea ERC1155
        await notify_sale(session, channel, s, collection_name, market, contract_or_slug)
        tx = s.get("txHash")
        if tx:
            seen_tx_hashes.add(tx)
            if len(seen_tx_hashes) > 2000:
                for _ in range(len(seen_tx_hashes) - 1500):
                    seen_tx_hashes.pop()

    return max(int(s.get("timestamp", 0)) for s in new_sales)
