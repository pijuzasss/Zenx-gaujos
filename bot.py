import asyncio
import json
import os
import re
import time
import unicodedata
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "")
CLIENT_ID = os.getenv("CLIENT_ID", "")
GUILD_ID_TEXT = os.getenv("GUILD_ID", "").strip()
GANG_TEXT = os.getenv("GANG_ROLE_TEXT", "gauja")
BOSS_TEXT = os.getenv("BOSS_ROLE_TEXT", "boss")
RIGHT_HAND_ROLE_NAME = os.getenv("RIGHT_HAND_ROLE_TEXT", "des.ranka")
BLACKLIST_ROLE_NAME = os.getenv("BLACKLIST_ROLE_TEXT", "black list")
BLACKLIST_ROLE_ID = os.getenv("BLACKLIST_ROLE_ID", "").strip()
COOLDOWN_ROLE_NAME = os.getenv("COOLDOWN_ROLE_NAME", "3d cooldown")
COOLDOWN_ROLE_ID = os.getenv("COOLDOWN_ROLE_ID", "").strip()
COOLDOWN_SECONDS = float(os.getenv("COOLDOWN_HOURS", "72")) * 3600
TICKET_CATEGORY_ID = os.getenv("TICKET_CATEGORY_ID", "").strip()
TICKET_SUPPORT_ROLE_ID = os.getenv("TICKET_SUPPORT_ROLE_ID", "").strip()
ROLE_REQUESTS_CHANNEL_ID = os.getenv("ROLE_REQUESTS_CHANNEL_ID", "").strip()

placeholders = {
    "DISCORD_TOKEN": (TOKEN, "IKLIJUOK_BOTO_TOKENA_CIA"),
    "CLIENT_ID": (CLIENT_ID, "IRASYK_APPLICATION_ID_CIA"),
    "GUILD_ID": (GUILD_ID_TEXT, "IRASYK_SERVERIO_ID_CIA"),
}
missing = [
    name for name, (value, placeholder) in placeholders.items()
    if not value or value == placeholder
]
if missing:
    raise RuntimeError(
        f"Atidaryk .env failą ir pakeisk šias reikšmes tikrais Discord duomenimis: {', '.join(missing)}"
    )
if not GUILD_ID_TEXT.isdigit():
    raise RuntimeError("GUILD_ID turi būti tik skaičiai, pavyzdžiui: GUILD_ID=123456789012345678")

GUILD_ID = int(GUILD_ID_TEXT)

DATA_DIRECTORY = Path(
    os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    or os.getenv("DATA_DIR")
    or (Path(__file__).parent / "data")
)
DATA_FILE = DATA_DIRECTORY / "state.json"
OLD_DATA_FILE = DATA_DIRECTORY / "cooldowns.json"


def normalize(text: str) -> str:
    small_caps = str.maketrans(
        "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ",
        "abcdefghijklmnopqrstuvwxyz",
    )
    decomposed = unicodedata.normalize("NFKD", text.casefold()).translate(small_caps)
    result = []
    for char in decomposed:
        codepoint = ord(char)
        # Discord rolėse naudojamos 🇦–🇿 regional-indicator raidės.
        if 0x1F1E6 <= codepoint <= 0x1F1FF:
            result.append(chr(ord("a") + codepoint - 0x1F1E6))
        elif not unicodedata.combining(char):
            result.append(char)
    return "".join(result)


def role_is_boss(role: discord.Role) -> bool:
    name = normalize(role.name)
    return (
        normalize(BOSS_TEXT) in name
        or "boss" in name
        or "bosas" in name
        or "boso" in name
    )


def role_is_right_hand(role: discord.Role) -> bool:
    return normalize(RIGHT_HAND_ROLE_NAME) in normalize(role.name)


def role_is_blacklist(role: discord.Role) -> bool:
    if BLACKLIST_ROLE_ID.isdigit() and role.id == int(BLACKLIST_ROLE_ID):
        return True
    configured = compact(BLACKLIST_ROLE_NAME)
    role_name = compact(role.name)
    return (configured and configured in role_name) or "blacklist" in role_name


COLOR_ALIASES = {
    "rozine": "roziniai",
    "rozinis": "roziniai",
    "roziniu": "roziniai",
    "roziniams": "roziniai",
    "raudona": "raudoni",
    "raudonas": "raudoni",
    "raudonu": "raudoni",
    "raudoniesiems": "raudoni",
    "balti": "balta",
    "baltas": "balta",
    "baltieji": "balta",
    "baltu": "balta",
    "smeline": "smeliniai",
    "smelinis": "smeliniai",
    "smeliniu": "smeliniai",
    "tmelyna": "tmelyni",
    "melyni": "tmelyni",
    "melyna": "tmelyni",
    "melynas": "tmelyni",
    "melynu": "tmelyni",
    "tamsiai-melyni": "tmelyni",
    "tamsiai-melyna": "tmelyni",
    "tamsiaimelyni": "tmelyni",
    "tamsiaimelyna": "tmelyni",
    "pilka": "pilki",
    "pilkas": "pilki",
    "pilku": "pilki",
    "zali": "zalia",
    "zalias": "zalia",
    "zaliu": "zalia",
    "juodi": "juoda",
    "juodas": "juoda",
    "juodu": "juoda",
    "zydras": "zydra",
    "zydri": "zydra",
    "zydru": "zydra",
    "violetine": "violetine",
    "violetiniai": "violetine",
    "violetinis": "violetine",
    "violetineje": "violetine",
    "violetiniu": "violetine",
    "oranzine": "oranziniai",
    "oranzinis": "oranziniai",
    "oranziniu": "oranziniai",
    "auksine": "auksiniai",
    "auksinis": "auksiniai",
    "auksiniu": "auksiniai",
    "bordine": "boordine",
    "bordo": "boordine",
    "boordiniai": "boordine",
    "boordinis": "boordine",
    "ruda": "rudi",
    "rudas": "rudi",
    "rudu": "rudi",
    "tzali": "tzalia",
    "tzalias": "tzalia",
    "tamsiai-zalia": "tzalia",
    "tamsiai-zali": "tzalia",
    "tamsiaizalia": "tzalia",
    "tamsiaizali": "tzalia",
    "dzinsine": "dzinsiniai",
    "dzinsinis": "dzinsiniai",
    "dzinsiniu": "dzinsiniai",
}


def compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", normalize(text))


def keyword_matches_role(keyword: str, role: discord.Role) -> bool:
    normalized_keyword = normalize(keyword)
    alias = COLOR_ALIASES.get(normalized_keyword, normalized_keyword)
    role_name = compact(role.name)
    return compact(alias) in role_name or compact(normalized_keyword) in role_name


def keywords_match_role(keywords: list[str], role: discord.Role) -> bool:
    if all(keyword_matches_role(keyword, role) for keyword in keywords):
        return True
    # Atpažįsta ir dviejų žodžių formas, pvz. „tamsiai zalia“.
    joined = "".join(compact(keyword) for keyword in keywords)
    return keyword_matches_role(joined, role)


def role_display_name(role: discord.Role) -> str:
    """Gaujos rolę rodo kaip tekstą „Gauja11“, jos nepažymėdamas."""
    gang_number = re.search(r"gauja\s*(\d+)", normalize(role.name))
    if gang_number:
        return f"Gauja{gang_number.group(1)}"
    return role.name


def find_cooldown_role(guild: discord.Guild) -> discord.Role | None:
    if COOLDOWN_ROLE_ID.isdigit():
        role = guild.get_role(int(COOLDOWN_ROLE_ID))
        if role:
            return role

    configured = normalize(COOLDOWN_ROLE_NAME)
    exact = discord.utils.find(
        lambda role: normalize(role.name) == configured, guild.roles
    )
    if exact:
        return exact

    # Atpažįsta ir stilizuotus pavadinimus, pvz. „﹒ᴄᴏᴏʟᴅᴏᴡɴ 3D“.
    return discord.utils.find(
        lambda role: "cooldown" in normalize(role.name)
        and ("3d" in normalize(role.name) or "3 d" in normalize(role.name)),
        guild.roles,
    )


async def get_or_create_cooldown_role(guild: discord.Guild) -> discord.Role:
    role = find_cooldown_role(guild)
    if role:
        return role
    return await guild.create_role(
        name=COOLDOWN_ROLE_NAME, reason="3 dienų gaujos cooldown rolė"
    )


def get_role_requests_channel(guild: discord.Guild) -> discord.TextChannel | None:
    if ROLE_REQUESTS_CHANNEL_ID.isdigit():
        configured_channel = guild.get_channel(int(ROLE_REQUESTS_CHANNEL_ID))
        if isinstance(configured_channel, discord.TextChannel):
            return configured_channel
    return discord.utils.find(
        lambda channel: compact(channel.name) == "rolesprasymai",
        guild.text_channels,
    )


async def reply_panel(
    message: discord.Message, text: str, success: bool = True
) -> discord.Message:
    embed = discord.Embed(
        description=text,
        color=discord.Color.green() if success else discord.Color.red(),
    )
    destination = get_role_requests_channel(message.guild) if message.guild else None

    if destination and destination.id != message.channel.id:
        return await destination.send(embed=embed)
    return await message.reply(embed=embed, mention_author=False)


TICKET_TYPES = {
    "gang_complaint": (
        "🚨 Gaujų skundas",
        "Pateikite skundą dėl gaujos ar jos narių.",
        "skundas",
    ),
    "gang_application": (
        "📋 Gaujų anketa",
        "Pildykite paraišką naujai gaujai.",
        "anketa",
    ),
    "pov_request": (
        "🎥 POV Prašymas",
        "Paprašykite POV / klipo iš kitos gaujos.",
        "pov",
    ),
    "help": (
        "❓ Pagalba",
        "Užduokite klausimą arba paprašykite pagalbos.",
        "pagalba",
    ),
}


def safe_channel_part(text: str) -> str:
    value = compact(text)[:20]
    return value or "narys"


async def get_ticket_category(guild: discord.Guild) -> discord.CategoryChannel:
    saved_config = state.get("ticketConfigs", {}).get(str(guild.id), {})
    saved_category_id = str(saved_config.get("categoryId", ""))
    if saved_category_id.isdigit():
        channel = guild.get_channel(int(saved_category_id))
        if isinstance(channel, discord.CategoryChannel):
            return channel
    if TICKET_CATEGORY_ID.isdigit():
        channel = guild.get_channel(int(TICKET_CATEGORY_ID))
        if isinstance(channel, discord.CategoryChannel):
            return channel
    existing = discord.utils.find(
        lambda category: normalize(category.name) == "tickets", guild.categories
    )
    if existing:
        return existing
    return await guild.create_category("TICKETS", reason="Ticket sistemos kategorija")


def get_ticket_support_role(guild: discord.Guild) -> discord.Role | None:
    saved_config = state.get("ticketConfigs", {}).get(str(guild.id), {})
    saved_role_id = str(saved_config.get("supportRoleId", ""))
    if saved_role_id.isdigit():
        role = guild.get_role(int(saved_role_id))
        if role:
            return role
    if TICKET_SUPPORT_ROLE_ID.isdigit():
        return guild.get_role(int(TICKET_SUPPORT_ROLE_ID))
    return None


class TicketCloseView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Uždaryti ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="ticket:close:v1",
    )
    async def close_ticket(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        del button
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not channel.topic:
            await interaction.response.send_message(
                "Šis kanalas nėra ticket.", ephemeral=True
            )
            return

        owner_match = re.search(r"ticket-owner:(\d+)", channel.topic)
        is_owner = bool(owner_match and int(owner_match.group(1)) == interaction.user.id)
        support_role = (
            get_ticket_support_role(interaction.guild) if interaction.guild else None
        )
        is_support = bool(
            isinstance(interaction.user, discord.Member)
            and support_role
            and support_role in interaction.user.roles
        )
        can_manage = interaction.permissions.manage_channels
        if not is_owner and not is_support and not can_manage:
            await interaction.response.send_message(
                "Šį ticket gali uždaryti jo autorius arba darbuotojas.", ephemeral=True
            )
            return

        await interaction.response.send_message("🔒 Ticket uždaromas po 3 sekundžių.")
        await asyncio.sleep(3)
        await channel.delete(reason=f"Ticket uždarė {interaction.user}")


class TicketTypeSelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(
                label="Gaujų skundas",
                description="Pateikti skundą dėl gaujos ar jos narių",
                emoji="🚨",
                value="gang_complaint",
            ),
            discord.SelectOption(
                label="Gaujų anketa",
                description="Pildyti paraišką naujai gaujai",
                emoji="📋",
                value="gang_application",
            ),
            discord.SelectOption(
                label="POV Prašymas",
                description="Paprašyti POV / klipo iš kitos gaujos",
                emoji="🎥",
                value="pov_request",
            ),
            discord.SelectOption(
                label="Pagalba",
                description="Klausimai ir kita pagalba",
                emoji="❓",
                value="help",
            ),
        ]
        super().__init__(
            placeholder="Pasirinkite tipą",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket:create:v1",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None or not isinstance(interaction.user, discord.Member):
            return
        await interaction.response.defer(ephemeral=True)

        existing = discord.utils.find(
            lambda channel: isinstance(channel, discord.TextChannel)
            and channel.topic is not None
            and f"ticket-owner:{interaction.user.id}" in channel.topic,
            guild.text_channels,
        )
        if existing:
            await interaction.followup.send(
                f"Jau turite atidarytą ticket: {existing.mention}", ephemeral=True
            )
            return

        ticket_type = self.values[0]
        title, description, channel_prefix = TICKET_TYPES[ticket_type]
        category = await get_ticket_category(guild)
        support_role = get_ticket_support_role(guild)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True,
            ),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            )

        channel = await guild.create_text_channel(
            f"{channel_prefix}-{safe_channel_part(interaction.user.display_name)}",
            category=category,
            overwrites=overwrites,
            topic=f"ticket-owner:{interaction.user.id};type:{ticket_type}",
            reason=f"Ticket sukūrė {interaction.user}",
        )
        embed = discord.Embed(
            title=title,
            description=(
                f"{interaction.user.mention}, aprašykite situaciją kuo išsamiau.\n\n"
                f"{description}\n\nDarbuotojai atsakys, kai galės."
            ),
            color=discord.Color.red(),
        )
        content = interaction.user.mention
        if support_role:
            content += f" {support_role.mention}"
        await channel.send(content=content, embed=embed, view=TicketCloseView())
        await interaction.followup.send(
            f"Ticket sukurtas: {channel.mention}", ephemeral=True
        )


class TicketPanelView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())


def ticket_access(interaction: discord.Interaction) -> tuple[bool, bool, bool]:
    """Grąžina: ar ticket kanalas, ar autorius, ar support/kanalų valdytojas."""
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel) or not channel.topic:
        return False, False, False
    owner_match = re.search(r"ticket-owner:(\d+)", channel.topic)
    if not owner_match:
        return False, False, False
    is_owner = int(owner_match.group(1)) == interaction.user.id
    support_role = (
        get_ticket_support_role(interaction.guild) if interaction.guild else None
    )
    is_support = bool(
        isinstance(interaction.user, discord.Member)
        and support_role
        and support_role in interaction.user.roles
    )
    is_staff = bool(is_support or interaction.permissions.manage_channels)
    return True, is_owner, is_staff


def load_state() -> dict:
    try:
        parsed = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return {
            "cooldowns": parsed.get("cooldowns", {}),
            "disbandJobs": parsed.get("disbandJobs", {}),
            "blacklists": parsed.get("blacklists", {}),
            "gangLeavers": parsed.get("gangLeavers", {}),
            "ticketConfigs": parsed.get("ticketConfigs", {}),
        }
    except (FileNotFoundError, json.JSONDecodeError):
        try:
            old = json.loads(OLD_DATA_FILE.read_text(encoding="utf-8"))
            return {
                "cooldowns": old,
                "disbandJobs": {},
                "blacklists": {},
                "gangLeavers": {},
                "ticketConfigs": {},
            }
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "cooldowns": {},
                "disbandJobs": {},
                "blacklists": {},
                "gangLeavers": {},
                "ticketConfigs": {},
            }


state = load_state()
state_lock = asyncio.Lock()
job_lock = asyncio.Lock()
cooldown_tasks: dict[str, asyncio.Task] = {}


def save_state_now() -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = DATA_FILE.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary, DATA_FILE)


async def save_state() -> None:
    async with state_lock:
        await asyncio.to_thread(save_state_now)


intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
persistent_views_registered = False


async def cooldown_worker(guild_id: int, user_id: int, expires_at: float) -> None:
    key = f"{guild_id}:{user_id}"
    try:
        await asyncio.sleep(max(0, expires_at - time.time()))
        entry = state["cooldowns"].get(key)
        if not entry or entry["expiresAt"] != expires_at:
            return

        guild = bot.get_guild(guild_id) or await bot.fetch_guild(guild_id)
        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except discord.NotFound:
                member = None
        role = guild.get_role(int(entry["roleId"]))
        if member and role and role in member.roles:
            await member.remove_roles(role, reason="3 dienų cooldown baigėsi")

        state["cooldowns"].pop(key, None)
        await save_state()
    except asyncio.CancelledError:
        raise
    except Exception as error:
        print(f"Nepavyko nuimti cooldown nuo {key}: {error}")
        await asyncio.sleep(60)
        schedule_cooldown(guild_id, user_id, expires_at)
    finally:
        if cooldown_tasks.get(key) is asyncio.current_task():
            cooldown_tasks.pop(key, None)


def schedule_cooldown(guild_id: int, user_id: int, expires_at: float) -> None:
    key = f"{guild_id}:{user_id}"
    old_task = cooldown_tasks.get(key)
    if old_task and old_task is not asyncio.current_task():
        old_task.cancel()
    cooldown_tasks[key] = asyncio.create_task(
        cooldown_worker(guild_id, user_id, expires_at)
    )


async def process_disband_jobs() -> None:
    async with job_lock:
        for job_id, job in list(state["disbandJobs"].items()):
            guild = bot.get_guild(int(job["guildId"]))
            if guild is None:
                continue

            cooldown_role = guild.get_role(int(job["cooldownRoleId"]))
            bot_member = guild.me
            if cooldown_role is None or bot_member is None:
                print(f"Disband darbas {job_id} laukia: nerasta cooldown arba boto rolė.")
                continue

            for user_id_text in list(job["pendingMemberIds"]):
                user_id = int(user_id_text)
                member = guild.get_member(user_id)
                if member is None:
                    try:
                        member = await guild.fetch_member(user_id)
                    except discord.NotFound:
                        job["pendingMemberIds"].remove(user_id_text)
                        await save_state()
                        continue

                key = f"{guild.id}:{user_id}"
                state["cooldowns"][key] = {
                    "roleId": str(cooldown_role.id),
                    "expiresAt": job["expiresAt"],
                }
                await save_state()

                try:
                    removable = [
                        role
                        for role in member.roles
                        if role != guild.default_role
                        and not role.managed
                        and role < bot_member.top_role
                    ]
                    if removable:
                        await member.remove_roles(
                            *removable,
                            reason=f"Tęsiamas gaujos išformavimas ({job['requestedBy']})",
                        )
                    if cooldown_role not in member.roles:
                        await member.add_roles(
                            cooldown_role,
                            reason="3 dienų cooldown po gaujos išformavimo",
                        )
                    schedule_cooldown(guild.id, user_id, job["expiresAt"])
                    job["pendingMemberIds"].remove(user_id_text)
                    job["completed"] += 1
                    await save_state()
                except discord.HTTPException as error:
                    print(f"Nepavyko apdoroti {member}: {error}")

            if not job["pendingMemberIds"]:
                state["disbandJobs"].pop(job_id, None)
                await save_state()


@bot.event
async def on_ready() -> None:
    global persistent_views_registered
    if not persistent_views_registered:
        bot.add_view(TicketPanelView())
        bot.add_view(TicketCloseView())
        persistent_views_registered = True

    guild_object = discord.Object(id=GUILD_ID)
    synced_commands = await bot.tree.sync(guild=guild_object)
    synced_names = ", ".join(f"/{command.name}" for command in synced_commands)
    print(f"Prisijungta kaip {bot.user}. Užregistruotos komandos: {synced_names}")

    for key, entry in list(state["cooldowns"].items()):
        guild_id, user_id = map(int, key.split(":"))
        expires_at = float(entry["expiresAt"])
        guild = bot.get_guild(guild_id)
        if guild and expires_at > time.time():
            member = guild.get_member(user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(user_id)
                except discord.NotFound:
                    member = None
            role = guild.get_role(int(entry["roleId"]))
            if member and (role is None or role not in member.roles):
                # Rolę rankiniu būdu nuėmė administratorius – termino neatkuriame.
                state["cooldowns"].pop(key, None)
                await save_state()
                continue
        schedule_cooldown(guild_id, user_id, expires_at)
    await process_disband_jobs()


@bot.event
async def on_member_remove(member: discord.Member) -> None:
    """Išsaugo tik apsaugines roles; gaujos ir kitos rolės nėra saugomos."""
    key = f"{member.guild.id}:{member.id}"
    blacklist_role = discord.utils.find(role_is_blacklist, member.roles)
    if blacklist_role:
        state["blacklists"][key] = {"roleId": str(blacklist_role.id)}
    else:
        state["blacklists"].pop(key, None)

    gang_roles = [
        role
        for role in member.roles
        if normalize(GANG_TEXT) in normalize(role.name)
        and not role_is_boss(role)
    ]
    if gang_roles:
        state["gangLeavers"][key] = {
            "gangRoleIds": [str(role.id) for role in gang_roles],
            "leftAt": time.time(),
        }
    else:
        state["gangLeavers"].pop(key, None)
    await save_state()


@bot.event
async def on_member_join(member: discord.Member) -> None:
    key = f"{member.guild.id}:{member.id}"
    roles_to_restore = []

    blacklist_entry = state["blacklists"].get(key)
    if blacklist_entry:
        blacklist_role = member.guild.get_role(int(blacklist_entry["roleId"]))
        if blacklist_role is None:
            blacklist_role = discord.utils.find(role_is_blacklist, member.guild.roles)
        if blacklist_role:
            roles_to_restore.append(blacklist_role)

    cooldown_entry = state["cooldowns"].get(key)
    left_with_gang = key in state["gangLeavers"]
    if cooldown_entry and float(cooldown_entry["expiresAt"]) <= time.time():
        state["cooldowns"].pop(key, None)
        cooldown_entry = None
        await save_state()

    if left_with_gang and not cooldown_entry:
        cooldown_role = await get_or_create_cooldown_role(member.guild)
        expires_at = time.time() + COOLDOWN_SECONDS
        cooldown_entry = {
            "roleId": str(cooldown_role.id),
            "expiresAt": expires_at,
        }
        state["cooldowns"][key] = cooldown_entry
        await save_state()

    if cooldown_entry:
        expires_at = float(cooldown_entry["expiresAt"])
        cooldown_role = member.guild.get_role(int(cooldown_entry["roleId"]))
        if cooldown_role is None:
            cooldown_role = find_cooldown_role(member.guild)
        if cooldown_role:
            roles_to_restore.append(cooldown_role)
            schedule_cooldown(member.guild.id, member.id, expires_at)

    if left_with_gang:
        state["gangLeavers"].pop(key, None)
        await save_state()

    if roles_to_restore:
        try:
            await member.add_roles(
                *roles_to_restore,
                reason="Atkurtos BLACKLIST / cooldown rolės nariui sugrįžus",
            )
        except discord.HTTPException as error:
            print(f"Nepavyko atkurti rolių sugrįžusiam nariui {member}: {error}")


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member) -> None:
    key = f"{after.guild.id}:{after.id}"
    before_blacklisted = any(role_is_blacklist(role) for role in before.roles)
    after_blacklisted = any(role_is_blacklist(role) for role in after.roles)
    if before_blacklisted and not after_blacklisted:
        state["blacklists"].pop(key, None)
        await save_state()

    entry = state["cooldowns"].get(key)
    if not entry:
        return

    cooldown_role_id = int(entry["roleId"])
    before_ids = {role.id for role in before.roles}
    after_ids = {role.id for role in after.roles}
    if cooldown_role_id in before_ids and cooldown_role_id not in after_ids:
        state["cooldowns"].pop(key, None)
        task = cooldown_tasks.pop(key, None)
        if task:
            task.cancel()
        await save_state()
        print(f"Cooldown rankiniu būdu atšauktas nariui {after}.")


@bot.event
async def on_message(message: discord.Message) -> None:
    if not message.guild or message.author.bot:
        return
    if not message.mentions:
        return
    if not isinstance(message.author, discord.Member):
        return

    command_text = re.sub(r"<@!?\d+>", " ", normalize(message.content))
    words = re.findall(r"[a-z0-9_.-]+", command_text)
    if "on" in words:
        action = "on"
    elif "off" in words:
        action = "off"
    else:
        return

    role_requests_channel = get_role_requests_channel(message.guild)
    if role_requests_channel is None or message.channel.id != role_requests_channel.id:
        # Už šio kanalo ribų komanda ignoruojama: neatsakome ir nekeičiame rolių.
        return

    target = message.mentions[0]
    right_hand_requested = action == "on" and any(
        word in {"des", "desine"} for word in words
    )
    ignored_words = {"on", "off", "des", "desine"}
    gang_keywords = [word for word in words if word not in ignored_words]

    author_gang_roles = [
        role
        for role in message.author.roles
        if normalize(GANG_TEXT) in normalize(role.name)
        and not role_is_boss(role)
    ]

    gang_role = None
    if gang_keywords:
        # Pirmiausia renkamės autoriaus turimą gaują – taip nepasirenkama svetima
        # panašaus pavadinimo rolė iš bendro serverio rolių sąrašo.
        gang_role = discord.utils.find(
            lambda role: keywords_match_role(gang_keywords, role),
            author_gang_roles,
        )
        if gang_role is None:
            gang_role = discord.utils.find(
                lambda role: normalize(GANG_TEXT) in normalize(role.name)
                and not role_is_boss(role)
                and keywords_match_role(gang_keywords, role),
                message.guild.roles,
            )
        if gang_role is None:
            await reply_panel(
                message,
                f"❌ Neradau gaujos rolės pagal pavadinimą `{ ' '.join(gang_keywords) }`.",
                False,
            )
            return
    elif author_gang_roles:
        gang_role = max(author_gang_roles, key=lambda role: role.position)

    if gang_role is None:
        await reply_panel(
            message,
            "❌ Neradau gaujos rolės. Parašyk gaujos pavadinimą, pvz. `@narys on raudoni`.",
            False,
        )
        return

    if action == "off":
        # Svetimos gaujos vadovas ar dešinė ranka negali nuimti kitos gaujos rolių.
        if gang_role not in target.roles:
            await reply_panel(
                message,
                "❌ Šis narys neturi tokios pačios gaujos rolės, todėl niekas nebuvo nuimta.",
                False,
            )
            return

        bot_member = message.guild.me
        related_roles = [
            role
            for role in target.roles
            if role == gang_role
            or role_is_boss(role)
            or role_is_right_hand(role)
        ]
        removable_roles = [
            role
            for role in related_roles
            if role != message.guild.default_role
            and not role.managed
            and bot_member is not None
            and role < bot_member.top_role
        ]
        try:
            cooldown_role = await get_or_create_cooldown_role(message.guild)

            expires_at = time.time() + COOLDOWN_SECONDS
            cooldown_key = f"{message.guild.id}:{target.id}"
            # Terminą įrašome prieš Discord pakeitimus, kad jis išliktų netikėtai išjungus botą.
            state["cooldowns"][cooldown_key] = {
                "roleId": str(cooldown_role.id),
                "expiresAt": expires_at,
            }
            await save_state()

            if removable_roles:
                await target.remove_roles(
                    *removable_roles,
                    reason=f"Iš gaujos pašalino {message.author} su @narys off",
                )
            await target.add_roles(
                cooldown_role,
                reason="3 dienų cooldown po pašalinimo iš gaujos",
            )
            schedule_cooldown(message.guild.id, target.id, expires_at)
            await reply_panel(
                message,
                f"✅ {target.mention} pašalintas iš {gang_role.mention} ir gavo 3 dienų cooldown.",
            )
        except discord.HTTPException:
            await reply_panel(
                message,
                "❌ Nepavyko pakeisti rolių. Patikrink boto teises ir rolių hierarchiją.",
                False,
            )
        return

    author_is_boss = any(role_is_boss(role) for role in message.author.roles)
    author_is_right_hand = any(
        role_is_right_hand(role) for role in message.author.roles
    )
    if not author_is_boss and not author_is_right_hand:
        await reply_panel(
            message,
            "❌ `on` komandą gali naudoti tik gaujos boss arba `des.ranka` rolę turintis narys.",
            False,
        )
        return

    # Ir boss, ir dešinė ranka gali priimti narius tik į savo gaują.
    if gang_role not in author_gang_roles:
        await reply_panel(
            message,
            "❌ Gali priimti narius tik į savo gaują.",
            False,
        )
        return

    cooldown_role = find_cooldown_role(message.guild)
    cooldown_key = f"{message.guild.id}:{target.id}"
    cooldown_entry = state["cooldowns"].get(cooldown_key)
    saved_cooldown_role = None
    if cooldown_entry:
        saved_cooldown_role = message.guild.get_role(int(cooldown_entry["roleId"]))

    has_cooldown_role = bool(
        (cooldown_role and cooldown_role in target.roles)
        or (saved_cooldown_role and saved_cooldown_role in target.roles)
    )

    # Jei adminas rankiniu būdu nuėmė rolę, laikome cooldown atšauktu ir
    # pašaliname seną terminą, kad jis nebūtų atkurtas po Railway deploy.
    if cooldown_entry and not has_cooldown_role:
        state["cooldowns"].pop(cooldown_key, None)
        cooldown_task = cooldown_tasks.pop(cooldown_key, None)
        if cooldown_task:
            cooldown_task.cancel()
        await save_state()
        cooldown_entry = None

    if has_cooldown_role:
        await reply_panel(message, "❌ Šiam nariui dar aktyvus 3 dienų cooldown.", False)
        return

    blacklist_role = discord.utils.find(
        role_is_blacklist, target.roles
    )
    if blacklist_role:
        await reply_panel(message, "❌ Šis narys turi black list rolę.", False)
        return

    target_gang_roles = [
        role
        for role in target.roles
        if normalize(GANG_TEXT) in normalize(role.name)
        and normalize(BOSS_TEXT) not in normalize(role.name)
    ]
    different_gang_roles = [role for role in target_gang_roles if role != gang_role]
    if different_gang_roles:
        await reply_panel(
            message,
            "❌ Šis narys jau turi kitos gaujos rolę, todėl jam nieko neuždėjau.",
            False,
        )
        return

    if not right_hand_requested and gang_role in target.roles:
        await reply_panel(message, f"❌ {target.mention} jau turi {gang_role.mention} rolę.", False)
        return

    roles_to_add = [gang_role]
    if right_hand_requested:
        configured_name = normalize(RIGHT_HAND_ROLE_NAME)
        right_hand_role = discord.utils.find(
            lambda role: normalize(role.name) == configured_name,
            message.guild.roles,
        )
        if right_hand_role is None:
            right_hand_role = discord.utils.find(
                lambda role: configured_name in normalize(role.name),
                message.guild.roles,
            )
        if right_hand_role is None:
            await reply_panel(
                message,
                f"❌ Neradau `{RIGHT_HAND_ROLE_NAME}` rolės.",
                False,
            )
            return
        # Jei gaujos dar neturi – uždedame gaują ir dešinę ranką; jei turi tą pačią – tik dešinę ranką.
        roles_to_add = [right_hand_role]
        if gang_role not in target.roles:
            roles_to_add.insert(0, gang_role)

    try:
        await target.add_roles(
            *roles_to_add, reason=f"Roles paskyrė {message.author} su on komanda"
        )
        role_names = ", ".join(role_display_name(role) for role in roles_to_add)
        await reply_panel(
            message,
            f"✅ {target.mention} sėkmingai pridėtas į {role_names}.",
        )
    except discord.HTTPException:
        await reply_panel(
            message,
            "❌ Nepavyko uždėti rolės. Patikrink boto teises ir rolių hierarchiją.",
            False,
        )


async def handle_disband(interaction: discord.Interaction, gauja: discord.Role) -> None:
    if not interaction.permissions.manage_roles:
        await interaction.response.send_message(
            "Šiai komandai reikia Manage Roles teisės.", ephemeral=True
        )
        return
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    if guild is None or gauja == guild.default_role or gauja.managed:
        await interaction.followup.send("Šios rolės negalima išformuoti.", ephemeral=True)
        return

    cooldown_role = await get_or_create_cooldown_role(guild)

    # Užkrauname visus serverio narius, kad disband nepraleistų necache'intų narių.
    await guild.chunk(cache=True)
    member_ids = [str(member.id) for member in gauja.members]
    job_id = f"{guild.id}:{int(time.time() * 1000)}"
    state["disbandJobs"][job_id] = {
        "guildId": str(guild.id),
        "gangRoleId": str(gauja.id),
        "cooldownRoleId": str(cooldown_role.id),
        "requestedBy": str(interaction.user),
        "expiresAt": time.time() + COOLDOWN_SECONDS,
        "pendingMemberIds": member_ids,
        "completed": 0,
    }
    await save_state()
    await process_disband_jobs()

    remaining = len(state["disbandJobs"].get(job_id, {}).get("pendingMemberIds", []))
    await interaction.followup.send(
        f"Išformuota: {len(member_ids) - remaining}/{len(member_ids)} narių. "
        f"Cooldown: {COOLDOWN_SECONDS / 3600:g} val.",
        ephemeral=True,
    )


async def send_ticket_panel(
    channel: discord.abc.Messageable, banner: discord.Attachment
) -> discord.Message:
    banner_file = await banner.to_file(filename="ticket-banner.png")
    embed = discord.Embed(
        title="Ticket pagalba",
        description="Pasirinkite ticketo tipą iš meniu žemiau.",
        color=discord.Color.red(),
    )
    embed.set_image(url="attachment://ticket-banner.png")
    embed.set_footer(text="Atsakome per 24 valandas • Nepagrįsti ticketai uždaromi")
    return await channel.send(
        embed=embed,
        file=banner_file,
        view=TicketPanelView(),
    )


@app_commands.command(
    name="ticket-add-member",
    description="Prideda žmogų į dabartinį ticket kanalą",
)
@app_commands.describe(member="Žmogus, kurį norite pridėti į ticket")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def ticket_add_member(
    interaction: discord.Interaction, member: discord.Member
) -> None:
    is_ticket, is_owner, is_staff = ticket_access(interaction)
    if not is_ticket:
        await interaction.response.send_message(
            "Šią komandą galima naudoti tik ticket kanale.", ephemeral=True
        )
        return
    if not is_owner and not is_staff:
        await interaction.response.send_message(
            "Žmogų gali pridėti ticket autorius arba darbuotojas.", ephemeral=True
        )
        return
    channel = interaction.channel
    await channel.set_permissions(
        member,
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        attach_files=True,
        reason=f"Į ticket pridėjo {interaction.user}",
    )
    await interaction.response.send_message(
        f"✅ {member.mention} pridėtas į ticket."
    )


@app_commands.command(
    name="ticket-add-role",
    description="Prideda rolę į dabartinį ticket kanalą",
)
@app_commands.describe(role="Rolė, kurią norite pridėti į ticket")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def ticket_add_role(
    interaction: discord.Interaction, role: discord.Role
) -> None:
    is_ticket, _is_owner, is_staff = ticket_access(interaction)
    if not is_ticket:
        await interaction.response.send_message(
            "Šią komandą galima naudoti tik ticket kanale.", ephemeral=True
        )
        return
    if not is_staff:
        await interaction.response.send_message(
            "Rolę gali pridėti tik support darbuotojas arba kanalų valdytojas.",
            ephemeral=True,
        )
        return
    if interaction.guild is None or role == interaction.guild.default_role:
        await interaction.response.send_message(
            "Saugumo sumetimais @everyone rolės pridėti negalima.", ephemeral=True
        )
        return
    channel = interaction.channel
    await channel.set_permissions(
        role,
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        attach_files=True,
        reason=f"Į ticket rolę pridėjo {interaction.user}",
    )
    await interaction.response.send_message(
        f"✅ Rolė {role.mention} pridėta į ticket.",
        allowed_mentions=discord.AllowedMentions(roles=False),
    )


@app_commands.command(
    name="setup-tickets",
    description="Automatiškai sukuria visą ticket sistemą",
)
@app_commands.describe(
    support_role="Darbuotojų rolė, kuri matys ir atsakys į ticketus",
    banner="Pagalbos centro bannerio paveikslėlis",
)
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def setup_tickets(
    interaction: discord.Interaction,
    support_role: discord.Role,
    banner: discord.Attachment,
) -> None:
    if not (
        interaction.permissions.manage_channels
        or interaction.permissions.manage_roles
        or interaction.permissions.administrator
    ):
        await interaction.response.send_message(
            "Šiai komandai reikia Manage Channels arba Manage Roles teisės.",
            ephemeral=True,
        )
        return
    if not banner.content_type or not banner.content_type.startswith("image/"):
        await interaction.response.send_message(
            "Banneris turi būti paveikslėlio failas.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    if guild is None or guild.me is None:
        return

    category = discord.utils.find(
        lambda item: normalize(item.name) == "tickets", guild.categories
    )
    if category is None:
        category = await guild.create_category(
            "TICKETS", reason=f"Ticket sistemą sukūrė {interaction.user}"
        )

    panel_channel = discord.utils.find(
        lambda item: normalize(item.name) == "ticket-pagalba",
        guild.text_channels,
    )
    panel_overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=False,
            read_message_history=True,
        ),
        support_role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            read_message_history=True,
            attach_files=True,
        ),
    }
    if panel_channel is None:
        panel_channel = await guild.create_text_channel(
            "ticket-pagalba",
            category=category,
            overwrites=panel_overwrites,
            reason=f"Ticket sistemą sukūrė {interaction.user}",
        )
    else:
        await panel_channel.edit(
            category=category,
            overwrites=panel_overwrites,
            reason=f"Ticket sistemą atnaujino {interaction.user}",
        )

    state["ticketConfigs"][str(guild.id)] = {
        "categoryId": str(category.id),
        "panelChannelId": str(panel_channel.id),
        "supportRoleId": str(support_role.id),
    }
    await save_state()
    panel = await send_ticket_panel(panel_channel, banner)
    await interaction.followup.send(
        f"Ticket sistema paruošta: {panel.jump_url}\n"
        f"Kategorija: `{category.name}` • Darbuotojai: {support_role.mention}",
        ephemeral=True,
    )


@app_commands.command(
    name="setup",
    description="Automatiškai sukuria visą ticket sistemą",
)
@app_commands.describe(
    support_role="Darbuotojų rolė, kuri matys ir atsakys į ticketus",
    banner="Pagalbos centro bannerio paveikslėlis",
)
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def setup(
    interaction: discord.Interaction,
    support_role: discord.Role,
    banner: discord.Attachment,
) -> None:
    await setup_tickets.callback(interaction, support_role, banner)


@app_commands.command(
    name="ticket-panel",
    description="Išsiunčia ticket sistemos panelę į šį kanalą",
)
@app_commands.describe(banner="Pagalbos centro bannerio paveikslėlis")
@app_commands.default_permissions(manage_channels=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def ticket_panel(
    interaction: discord.Interaction, banner: discord.Attachment
) -> None:
    if not interaction.permissions.manage_channels:
        await interaction.response.send_message(
            "Šiai komandai reikia Manage Channels teisės.", ephemeral=True
        )
        return
    if not banner.content_type or not banner.content_type.startswith("image/"):
        await interaction.response.send_message(
            "Banneris turi būti paveikslėlio failas.", ephemeral=True
        )
        return
    if interaction.channel is None:
        return

    await interaction.response.defer(ephemeral=True)
    panel = await send_ticket_panel(interaction.channel, banner)
    await interaction.followup.send(
        f"Ticket panelė sukurta: {panel.jump_url}", ephemeral=True
    )


@app_commands.command(
    name="disband", description="Išformuoja gaują ir uždeda 3 dienų cooldown"
)
@app_commands.describe(gauja="Gaujos rolė, kurios narius reikia išformuoti")
@app_commands.default_permissions(manage_roles=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def disband(interaction: discord.Interaction, gauja: discord.Role) -> None:
    await handle_disband(interaction, gauja)


@app_commands.command(
    name="disban", description="Išformuoja gaują ir uždeda 3 dienų cooldown"
)
@app_commands.describe(gauja="Gaujos rolė, kurios narius reikia išformuoti")
@app_commands.default_permissions(manage_roles=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def disban(interaction: discord.Interaction, gauja: discord.Role) -> None:
    await handle_disband(interaction, gauja)


bot.tree.add_command(setup_tickets)
bot.tree.add_command(setup)
bot.tree.add_command(ticket_panel)
bot.tree.add_command(ticket_add_member)
bot.tree.add_command(ticket_add_role)
bot.tree.add_command(disband)
bot.run(TOKEN)
