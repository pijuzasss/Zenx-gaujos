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
BOSS_ROLE_ID = os.getenv("BOSS_ROLE_ID", "").strip()
RIGHT_HAND_ROLE_NAME = os.getenv("RIGHT_HAND_ROLE_TEXT", "des.ranka")
BLACKLIST_ROLE_NAME = os.getenv("BLACKLIST_ROLE_TEXT", "black list")
BLACKLIST_ROLE_ID = os.getenv("BLACKLIST_ROLE_ID", "").strip()
COOLDOWN_ROLE_NAME = os.getenv("COOLDOWN_ROLE_NAME", "3d cooldown")
COOLDOWN_ROLE_ID = os.getenv("COOLDOWN_ROLE_ID", "").strip()
COOLDOWN_SECONDS = float(os.getenv("COOLDOWN_HOURS", "72")) * 3600
TICKET_CATEGORY_ID = os.getenv("TICKET_CATEGORY_ID", "").strip()
TICKET_SUPPORT_ROLE_ID = os.getenv("TICKET_SUPPORT_ROLE_ID", "").strip()
ROLE_REQUESTS_CHANNEL_ID = os.getenv("ROLE_REQUESTS_CHANNEL_ID", "").strip()
GANG_MEMBER_LIMIT = int(os.getenv("GANG_MEMBER_LIMIT", "20"))
RECRUITMENT_CHANNEL_ID = os.getenv("RECRUITMENT_CHANNEL_ID", "").strip()

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
        f"Atidaryk .env failÄ… ir pakeisk Å¡ias reikÅ¡mes tikrais Discord duomenimis: {', '.join(missing)}"
    )
if not GUILD_ID_TEXT.isdigit():
    raise RuntimeError("GUILD_ID turi bÅ«ti tik skaiÄiai, pavyzdÅ¾iui: GUILD_ID=123456789012345678")

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
        "á´€Ê™á´„á´…á´‡êœ°É¢ÊœÉªá´Šá´‹ÊŸá´É´á´á´˜Ç«Ê€êœ±á´›á´œá´ á´¡xÊá´¢",
        "abcdefghijklmnopqrstuvwxyz",
    )
    decomposed = unicodedata.normalize("NFKD", text.casefold()).translate(small_caps)
    result = []
    for char in decomposed:
        codepoint = ord(char)
        # Discord rolÄ—se naudojamos ðŸ‡¦â€“ðŸ‡¿ regional-indicator raidÄ—s.
        if 0x1F1E6 <= codepoint <= 0x1F1FF:
            result.append(chr(ord("a") + codepoint - 0x1F1E6))
        elif not unicodedata.combining(char):
            result.append(char)
    return "".join(result)


def role_is_boss(role: discord.Role) -> bool:
    if BOSS_ROLE_ID.isdigit() and role.id == int(BOSS_ROLE_ID):
        return True
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
    # AtpaÅ¾Ä¯sta ir dviejÅ³ Å¾odÅ¾iÅ³ formas, pvz. â€žtamsiai zaliaâ€œ.
    joined = "".join(compact(keyword) for keyword in keywords)
    return keyword_matches_role(joined, role)


def role_display_name(role: discord.Role) -> str:
    """Gaujos rolÄ™ rodo kaip tekstÄ… â€žGauja11â€œ, jos nepaÅ¾ymÄ—damas."""
    gang_number = re.search(r"gauja\s*(\d+)", normalize(role.name))
    if gang_number:
        return f"Gauja{gang_number.group(1)}"
    return role.name


def gang_member_count_text(role: discord.Role) -> str:
    return f"({len(role.members)}/{GANG_MEMBER_LIMIT} nariu)"


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

    # AtpaÅ¾Ä¯sta ir stilizuotus pavadinimus, pvz. â€žï¹’á´„á´á´ÊŸá´…á´á´¡É´ 3Dâ€œ.
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
        name=COOLDOWN_ROLE_NAME, reason="3 dienÅ³ gaujos cooldown rolÄ—"
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


async def update_member_status(guild: discord.Guild | None = None) -> None:
    guild = guild or bot.get_guild(GUILD_ID)
    if guild is None:
        return
    member_count = guild.member_count or len(guild.members)
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{member_count} zmoniu serveryje",
        )
    )


def get_recruitment_channel(guild: discord.Guild) -> discord.TextChannel | None:
    if RECRUITMENT_CHANNEL_ID.isdigit():
        channel = guild.get_channel(int(RECRUITMENT_CHANNEL_ID))
        if isinstance(channel, discord.TextChannel):
            return channel
    return None


def member_has_boss_role(member: discord.Member) -> bool:
    return any(role_is_boss(role) for role in member.roles)


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
        "ðŸš¨ GaujÅ³ skundas",
        "Pateikite skundÄ… dÄ—l gaujos ar jos nariÅ³.",
        "skundas",
    ),
    "pov_request": (
        "ðŸŽ¥ POV PraÅ¡ymas",
        "PapraÅ¡ykite POV / klipo iÅ¡ kitos gaujos.",
        "pov",
    ),
    "help": (
        "â“ Pagalba",
        "UÅ¾duokite klausimÄ… arba papraÅ¡ykite pagalbos.",
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
        label="UÅ¾daryti ticket",
        style=discord.ButtonStyle.danger,
        emoji="ðŸ”’",
        custom_id="ticket:close:v1",
    )
    async def close_ticket(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        del button
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not channel.topic:
            await interaction.response.send_message(
                "Å is kanalas nÄ—ra ticket.", ephemeral=True
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
                "Å Ä¯ ticket gali uÅ¾daryti jo autorius arba darbuotojas.", ephemeral=True
            )
            return

        await interaction.response.send_message("ðŸ”’ Ticket uÅ¾daromas po 3 sekundÅ¾iÅ³.")
        await asyncio.sleep(3)
        await channel.delete(reason=f"Ticket uÅ¾darÄ— {interaction.user}")


class TicketTypeSelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(
                label="GaujÅ³ skundas",
                description="Pateikti skundÄ… dÄ—l gaujos ar jos nariÅ³",
                value="gang_complaint",
            ),
            discord.SelectOption(
                label="POV PraÅ¡ymas",
                description="PapraÅ¡yti POV / klipo iÅ¡ kitos gaujos",
                value="pov_request",
            ),
            discord.SelectOption(
                label="Pagalba",
                description="Klausimai ir kita pagalba",
                value="help",
            ),
        ]
        super().__init__(
            placeholder="Pasirinkite kategorija",
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
                f"Jau turite atidarytÄ… ticket: {existing.mention}", ephemeral=True
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
            reason=f"Ticket sukÅ«rÄ— {interaction.user}",
        )
        embed = discord.Embed(
            title=title,
            description=(
                f"{interaction.user.mention}, apraÅ¡ykite situacijÄ… kuo iÅ¡samiau.\n\n"
                f"{description}\n\nDarbuotojai atsakys, kai galÄ—s."
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
    """GrÄ…Å¾ina: ar ticket kanalas, ar autorius, ar support/kanalÅ³ valdytojas."""
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
color_change_lock = asyncio.Lock()
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
cooldown_sweeper_started = False


async def expire_cooldown_now(guild_id: int, user_id: int, expires_at: float) -> bool:
    key = f"{guild_id}:{user_id}"
    entry = state["cooldowns"].get(key)
    if not entry or float(entry["expiresAt"]) != float(expires_at):
        return True

    guild = bot.get_guild(guild_id) or await bot.fetch_guild(guild_id)
    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except discord.NotFound:
            member = None

    roles_to_remove = []
    saved_role = guild.get_role(int(entry["roleId"]))
    current_role = find_cooldown_role(guild)
    matching_roles = [
        role
        for role in guild.roles
        if "cooldown" in normalize(role.name)
        and ("3d" in normalize(role.name) or "3 d" in normalize(role.name))
    ]
    for role in (saved_role, current_role, *matching_roles):
        if member and role and role in member.roles and role not in roles_to_remove:
            roles_to_remove.append(role)

    if member and roles_to_remove:
        await member.remove_roles(*roles_to_remove, reason="3 dienu cooldown baigesi")

    state["cooldowns"].pop(key, None)
    await save_state()
    return True


async def cooldown_worker(guild_id: int, user_id: int, expires_at: float) -> None:
    key = f"{guild_id}:{user_id}"
    try:
        await asyncio.sleep(max(0, expires_at - time.time()))
        entry = state["cooldowns"].get(key)
        if not entry or entry["expiresAt"] != expires_at:
            return

        await expire_cooldown_now(guild_id, user_id, expires_at)
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
            await member.remove_roles(role, reason="3 dienÅ³ cooldown baigÄ—si")

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


async def sweep_expired_cooldowns() -> None:
    while not bot.is_closed():
        now = time.time()
        for key, entry in list(state["cooldowns"].items()):
            try:
                expires_at = float(entry["expiresAt"])
                if expires_at <= now:
                    guild_id_text, user_id_text = key.split(":")
                    await expire_cooldown_now(
                        int(guild_id_text),
                        int(user_id_text),
                        expires_at,
                    )
            except Exception as error:
                print(f"Cooldown sweep nepavyko sutvarkyti {key}: {error}")
        await asyncio.sleep(600)


async def process_disband_jobs() -> None:
    async with job_lock:
        for job_id, job in list(state["disbandJobs"].items()):
            guild = bot.get_guild(int(job["guildId"]))
            if guild is None:
                continue

            cooldown_role = guild.get_role(int(job["cooldownRoleId"]))
            bot_member = guild.me
            if cooldown_role is None or bot_member is None:
                print(f"Disband darbas {job_id} laukia: nerasta cooldown arba boto rolÄ—.")
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
                    async def disband_member() -> None:
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
                            reason=f"TÄ™siamas gaujos iÅ¡formavimas ({job['requestedBy']})",
                            )
                        if cooldown_role not in member.roles:
                            await member.add_roles(
                                cooldown_role,
                            reason="3 dienÅ³ cooldown po gaujos iÅ¡formavimo",
                            )
                    await asyncio.wait_for(disband_member(), timeout=30)
                    schedule_cooldown(guild.id, user_id, job["expiresAt"])
                    job["pendingMemberIds"].remove(user_id_text)
                    job["completed"] += 1
                    await save_state()
                except (discord.HTTPException, asyncio.TimeoutError) as error:
                    print(f"Nepavyko apdoroti {member}: {error}")

            if not job["pendingMemberIds"]:
                state["disbandJobs"].pop(job_id, None)
                await save_state()


@bot.event
async def on_ready() -> None:
    global persistent_views_registered, cooldown_sweeper_started
    if not persistent_views_registered:
        bot.add_view(TicketPanelView())
        bot.add_view(TicketCloseView())
        persistent_views_registered = True
    if not cooldown_sweeper_started:
        asyncio.create_task(sweep_expired_cooldowns())
        cooldown_sweeper_started = True

    guild_object = discord.Object(id=GUILD_ID)
    synced_commands = await bot.tree.sync(guild=guild_object)
    synced_names = ", ".join(f"/{command.name}" for command in synced_commands)
    await update_member_status()
    print(f"Prisijungta kaip {bot.user}. UÅ¾registruotos komandos: {synced_names}")

    for key, entry in list(state["cooldowns"].items()):
        guild_id, user_id = map(int, key.split(":"))
        expires_at = float(entry["expiresAt"])
        if expires_at <= time.time():
            try:
                await expire_cooldown_now(guild_id, user_id, expires_at)
            except Exception as error:
                print(f"Nepavyko iskart nuimti pasibaigusio cooldown nuo {key}: {error}")
            continue

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
                # RolÄ™ rankiniu bÅ«du nuÄ—mÄ— administratorius â€“ termino neatkuriame.
                state["cooldowns"].pop(key, None)
                await save_state()
                continue
        schedule_cooldown(guild_id, user_id, expires_at)
    asyncio.create_task(process_disband_jobs())


@bot.event
async def on_member_remove(member: discord.Member) -> None:
    """IÅ¡saugo tik apsaugines roles; gaujos ir kitos rolÄ—s nÄ—ra saugomos."""
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
    await update_member_status(member.guild)


@bot.event
async def on_member_join(member: discord.Member) -> None:
    await update_member_status(member.guild)
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
                reason="Atkurtos BLACKLIST / cooldown rolÄ—s nariui sugrÄ¯Å¾us",
            )
        except discord.HTTPException as error:
            print(f"Nepavyko atkurti roliÅ³ sugrÄ¯Å¾usiam nariui {member}: {error}")


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member) -> None:
    key = f"{after.guild.id}:{after.id}"
    before_ids = {role.id for role in before.roles}
    after_ids = {role.id for role in after.roles}
    before_blacklisted = any(role_is_blacklist(role) for role in before.roles)
    after_blacklisted = any(role_is_blacklist(role) for role in after.roles)
    if before_blacklisted and not after_blacklisted:
        state["blacklists"].pop(key, None)
        await save_state()

    cooldown_role = find_cooldown_role(after.guild)
    if (
        cooldown_role
        and cooldown_role.id not in before_ids
        and cooldown_role.id in after_ids
    ):
        entry = state["cooldowns"].get(key)
        if entry and float(entry["expiresAt"]) > time.time():
            expires_at = float(entry["expiresAt"])
        else:
            expires_at = time.time() + COOLDOWN_SECONDS
        state["cooldowns"][key] = {
            "roleId": str(cooldown_role.id),
            "expiresAt": expires_at,
        }
        await save_state()
        schedule_cooldown(after.guild.id, after.id, expires_at)
        print(f"Nariui {after} automatiÅ¡kai pradÄ—tas 3 dienÅ³ cooldown.")

    entry = state["cooldowns"].get(key)
    if not entry:
        return

    cooldown_role_id = int(entry["roleId"])
    if cooldown_role_id in before_ids and cooldown_role_id not in after_ids:
        state["cooldowns"].pop(key, None)
        task = cooldown_tasks.pop(key, None)
        if task:
            task.cancel()
        await save_state()
        print(f"Cooldown rankiniu bÅ«du atÅ¡auktas nariui {after}.")


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
        # UÅ¾ Å¡io kanalo ribÅ³ komanda ignoruojama: neatsakome ir nekeiÄiame roliÅ³.
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
        # Pirmiausia renkamÄ—s autoriaus turimÄ… gaujÄ… â€“ taip nepasirenkama svetima
        # panaÅ¡aus pavadinimo rolÄ— iÅ¡ bendro serverio roliÅ³ sÄ…raÅ¡o.
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
                f"âŒ Neradau gaujos rolÄ—s pagal pavadinimÄ… `{ ' '.join(gang_keywords) }`.",
                False,
            )
            return
    elif author_gang_roles:
        gang_role = max(author_gang_roles, key=lambda role: role.position)

    if gang_role is None:
        await reply_panel(
            message,
            "âŒ Neradau gaujos rolÄ—s. ParaÅ¡yk gaujos pavadinimÄ…, pvz. `@narys on raudoni`.",
            False,
        )
        return

    if action == "off":
        # Svetimos gaujos vadovas ar deÅ¡inÄ— ranka negali nuimti kitos gaujos roliÅ³.
        if gang_role not in target.roles:
            await reply_panel(
                message,
                "âŒ Å is narys neturi tokios paÄios gaujos rolÄ—s, todÄ—l niekas nebuvo nuimta.",
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
            # TerminÄ… Ä¯raÅ¡ome prieÅ¡ Discord pakeitimus, kad jis iÅ¡liktÅ³ netikÄ—tai iÅ¡jungus botÄ….
            state["cooldowns"][cooldown_key] = {
                "roleId": str(cooldown_role.id),
                "expiresAt": expires_at,
            }
            await save_state()

            if removable_roles:
                await target.remove_roles(
                    *removable_roles,
                    reason=f"IÅ¡ gaujos paÅ¡alino {message.author} su @narys off",
                )
            await target.add_roles(
                cooldown_role,
                reason="3 dienÅ³ cooldown po paÅ¡alinimo iÅ¡ gaujos",
            )
            schedule_cooldown(message.guild.id, target.id, expires_at)
            await reply_panel(
                message,
                f"âœ… {target.mention} pasalintas is {role_display_name(gang_role)}. {gang_member_count_text(gang_role)}",
            )
        except discord.HTTPException:
            await reply_panel(
                message,
                "âŒ Nepavyko pakeisti roliÅ³. Patikrink boto teises ir roliÅ³ hierarchijÄ….",
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
            "âŒ `on` komandÄ… gali naudoti tik gaujos boss arba `des.ranka` rolÄ™ turintis narys.",
            False,
        )
        return

    # Ir boss, ir deÅ¡inÄ— ranka gali priimti narius tik Ä¯ savo gaujÄ….
    if gang_role not in author_gang_roles:
        await reply_panel(
            message,
            "âŒ Gali priimti narius tik Ä¯ savo gaujÄ….",
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

    # Jei adminas rankiniu bÅ«du nuÄ—mÄ— rolÄ™, laikome cooldown atÅ¡auktu ir
    # paÅ¡aliname senÄ… terminÄ…, kad jis nebÅ«tÅ³ atkurtas po Railway deploy.
    if cooldown_entry and not has_cooldown_role:
        state["cooldowns"].pop(cooldown_key, None)
        cooldown_task = cooldown_tasks.pop(cooldown_key, None)
        if cooldown_task:
            cooldown_task.cancel()
        await save_state()
        cooldown_entry = None

    if has_cooldown_role:
        await reply_panel(message, "âŒ Å iam nariui dar aktyvus 3 dienÅ³ cooldown.", False)
        return

    blacklist_role = discord.utils.find(
        role_is_blacklist, target.roles
    )
    if blacklist_role:
        await reply_panel(message, "âŒ Å is narys turi black list rolÄ™.", False)
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
            "âŒ Å is narys jau turi kitos gaujos rolÄ™, todÄ—l jam nieko neuÅ¾dÄ—jau.",
            False,
        )
        return

    if not right_hand_requested and gang_role in target.roles:
        await reply_panel(message, f"âŒ {target.mention} jau turi {role_display_name(gang_role)} role.", False)
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
                f"âŒ Neradau `{RIGHT_HAND_ROLE_NAME}` rolÄ—s.",
                False,
            )
            return
        # Jei gaujos dar neturi â€“ uÅ¾dedame gaujÄ… ir deÅ¡inÄ™ rankÄ…; jei turi tÄ… paÄiÄ… â€“ tik deÅ¡inÄ™ rankÄ….
        roles_to_add = [right_hand_role]
        if gang_role not in target.roles:
            roles_to_add.insert(0, gang_role)

    try:
        await target.add_roles(
            *roles_to_add, reason=f"Roles paskyrÄ— {message.author} su on komanda"
        )
        role_names = ", ".join(role_display_name(role) for role in roles_to_add)
        await reply_panel(
            message,
            f"âœ… {target.mention} sekmingai pridetas i {role_names}. {gang_member_count_text(gang_role)}",
        )
    except discord.HTTPException:
        await reply_panel(
            message,
            "âŒ Nepavyko uÅ¾dÄ—ti rolÄ—s. Patikrink boto teises ir roliÅ³ hierarchijÄ….",
            False,
        )


async def apply_gang_color_change(
    guild: discord.Guild,
    old_role: discord.Role,
    new_role: discord.Role,
    requested_by: discord.abc.User,
) -> tuple[int, list[str]]:
    async with color_change_lock:
        bot_member = guild.me
        if bot_member is None:
            return 0, ["Nepavyko rasti boto nario serveryje"]
        if old_role >= bot_member.top_role or new_role >= bot_member.top_role:
            return 0, ["Boto rolÄ— turi bÅ«ti aukÅ¡Äiau uÅ¾ abi gaujÅ³ roles"]

        members = list(old_role.members)
        completed = 0
        failures = []
        for member in members:
            try:
                async def change_member_roles() -> None:
                    if new_role not in member.roles:
                        await member.add_roles(
                            new_role,
                            reason=f"Gaujos spalvÄ… pakeitÄ— {requested_by}",
                        )
                    if old_role in member.roles:
                        await member.remove_roles(
                            old_role,
                            reason=f"Gaujos spalvÄ… pakeitÄ— {requested_by}",
                        )

                await asyncio.wait_for(change_member_roles(), timeout=30)
                completed += 1
            except (discord.HTTPException, asyncio.TimeoutError):
                failures.append(str(member))
        return completed, failures


class ColorChangeConfirmView(discord.ui.View):
    def __init__(
        self, requester_id: int, old_role_id: int, new_role_id: int
    ) -> None:
        super().__init__(timeout=60)
        self.requester_id = requester_id
        self.old_role_id = old_role_id
        self.new_role_id = new_role_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "Å Ä¯ pasirinkimÄ… gali patvirtinti tik komandÄ… paleidÄ™s administratorius.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="TÄ™sti keitimÄ…", style=discord.ButtonStyle.danger, emoji="âš ï¸")
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        del button
        guild = interaction.guild
        if guild is None:
            return
        old_role = guild.get_role(self.old_role_id)
        new_role = guild.get_role(self.new_role_id)
        if old_role is None or new_role is None:
            await interaction.response.edit_message(
                content="Viena iÅ¡ gaujos roliÅ³ buvo iÅ¡trinta. Keitimas atÅ¡auktas.",
                embed=None,
                view=None,
            )
            return
        await interaction.response.edit_message(
            content="â³ Gaujos spalva keiÄiama, palaukite...",
            embed=None,
            view=None,
        )
        completed, failures = await apply_gang_color_change(
            guild, old_role, new_role, interaction.user
        )
        failure_text = (
            f"\nNepavyko pakeisti {len(failures)} nariÅ³: {', '.join(failures[:10])}"
            if failures
            else ""
        )
        await interaction.edit_original_response(
            content=(
                f"âœ… Perkelta nariÅ³: **{completed}**. "
                f"`{old_role.name}` â†’ `{new_role.name}`.\n"
                "Boss, des.ranka ir visos kitos rolÄ—s paliktos nepakeistos."
                f"{failure_text}"
            ),
            embed=None,
            view=None,
        )

    @discord.ui.button(label="AtÅ¡aukti", style=discord.ButtonStyle.secondary, emoji="âœ–ï¸")
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        del button
        await interaction.response.edit_message(
            content="Spalvos keitimas atÅ¡auktas.", embed=None, view=None
        )


async def handle_disband(interaction: discord.Interaction, gauja: discord.Role) -> None:
    if not interaction.permissions.manage_roles:
        await interaction.response.send_message(
            "Å iai komandai reikia Manage Roles teisÄ—s.", ephemeral=True
        )
        return
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    if guild is None or gauja == guild.default_role or gauja.managed:
        await interaction.followup.send("Å ios rolÄ—s negalima iÅ¡formuoti.", ephemeral=True)
        return

    cooldown_role = await get_or_create_cooldown_role(guild)

    # UÅ¾krauname visus serverio narius, kad disband nepraleistÅ³ necache'intÅ³ nariÅ³.
    try:
        await asyncio.wait_for(guild.chunk(cache=True), timeout=10)
    except asyncio.TimeoutError:
        print("Disband: nariu uzkrovimas uztruko per ilgai; naudojamas esamas cache.")
    member_ids = [str(member.id) for member in gauja.members]
    if not member_ids:
        await interaction.followup.send(
            "Neradau nariu su sia gaujos role. Patikrink Server Members Intent ir ar pasirinkai tinkama role.",
            ephemeral=True,
        )
        return
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
    asyncio.create_task(process_disband_jobs())
    await interaction.followup.send(
        f"Disband pradetas fone: {len(member_ids)} nariu. "
        f"Cooldown: {COOLDOWN_SECONDS / 3600:g} val. Progresas issaugomas po kiekvieno nario.",
        ephemeral=True,
    )
    return

    remaining = len(state["disbandJobs"].get(job_id, {}).get("pendingMemberIds", []))
    await interaction.followup.send(
        f"IÅ¡formuota: {len(member_ids) - remaining}/{len(member_ids)} nariÅ³. "
        f"Cooldown: {COOLDOWN_SECONDS / 3600:g} val.",
        ephemeral=True,
    )


async def send_ticket_panel(
    channel: discord.abc.Messageable, banner: discord.Attachment
) -> discord.Message:
    banner_file = await banner.to_file(filename="ticket-banner.png")
    embed = discord.Embed(
        title="ZENX GAUJU BILIETAI",
        description=(
            "**Sveikas! Jeigu atsidurete cia, greiciausiai turite klausimu arba "
            "susidurete su problema, kuriai reikalinga musu pagalba.**\n\n"
            "> Noredami pradeti, pasirinkite viena is zemiau esanciu kategoriju, "
            "kuri geriausiai atitinka jusu situacija. Kuo tiksliau aprasysite "
            "savo problema, tuo greiciau ir efektyviau galesime jums padeti.\n"
            "> Musu administracijos komanda perziures jusu uzklausa ir susisieks "
            "su jumis kaip imanoma greiciau.\n\n"
            "**Dekojame uz kantrybe ir linkime malonios dienos! ❤️**"
        ),
        color=discord.Color(0x2B2D31),
    )
    embed.set_image(url="attachment://ticket-banner.png")
    return await channel.send(
        embed=embed,
        file=banner_file,
        view=TicketPanelView(),
    )


@app_commands.command(
    name="pakeisti-spalva",
    description="Perkelia visus vienos gaujos narius Ä¯ kitos spalvos gaujÄ…",
)
@app_commands.describe(
    sena_gauja="DabartinÄ— gaujos rolÄ—",
    nauja_gauja="Nauja gaujos spalvos rolÄ—",
)
@app_commands.default_permissions(manage_roles=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def pakeisti_spalva(
    interaction: discord.Interaction,
    sena_gauja: discord.Role,
    nauja_gauja: discord.Role,
) -> None:
    if not interaction.permissions.manage_roles:
        await interaction.response.send_message(
            "Å iai komandai reikia Manage Roles teisÄ—s.", ephemeral=True
        )
        return
    if interaction.guild is None:
        return
    if sena_gauja == nauja_gauja:
        await interaction.response.send_message(
            "Sena ir nauja gaujos rolÄ—s negali bÅ«ti vienodos.", ephemeral=True
        )
        return
    invalid_role = any(
        role == interaction.guild.default_role
        or role.managed
        or normalize(GANG_TEXT) not in normalize(role.name)
        or role_is_boss(role)
        for role in (sena_gauja, nauja_gauja)
    )
    if invalid_role:
        await interaction.response.send_message(
            "Pasirink abi tikras gaujÅ³ roles (pvz. `// Å½ALIA // GAUJA7`), ne boss ar integracijos rolÄ™.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)
    try:
        await asyncio.wait_for(interaction.guild.chunk(cache=True), timeout=10)
    except asyncio.TimeoutError:
        print("NariÅ³ sÄ…raÅ¡o uÅ¾krovimas uÅ¾truko per ilgai; naudojamas esamas cache.")
    target_members = list(nauja_gauja.members)
    if target_members:
        preview = ", ".join(str(member) for member in target_members[:10])
        extra = (
            f" ir dar {len(target_members) - 10}"
            if len(target_members) > 10
            else ""
        )
        warning = discord.Embed(
            title="âš ï¸ Naujoje gaujoje jau yra Å¾moniÅ³",
            description=(
                f"RolÄ™ `{nauja_gauja.name}` jau turi **{len(target_members)}** nariÅ³.\n"
                f"Nariai: {preview}{extra}\n\n"
                f"Ar tikrai norite perkelti visus iÅ¡ `{sena_gauja.name}`?"
            ),
            color=discord.Color.orange(),
        )
        await interaction.followup.send(
            embed=warning,
            view=ColorChangeConfirmView(
                interaction.user.id, sena_gauja.id, nauja_gauja.id
            ),
            ephemeral=True,
        )
        return

    status_message = await interaction.followup.send(
        "â³ Gaujos spalva keiÄiama, palaukite...",
        ephemeral=True,
        wait=True,
    )
    completed, failures = await apply_gang_color_change(
        interaction.guild, sena_gauja, nauja_gauja, interaction.user
    )
    failure_text = (
        f" Nepavyko pakeisti {len(failures)} nariÅ³: {', '.join(failures[:10])}."
        if failures
        else ""
    )
    await status_message.edit(
        content=(
        f"âœ… Perkelta nariÅ³: **{completed}**. "
        f"`{sena_gauja.name}` â†’ `{nauja_gauja.name}`. "
        f"Boss, des.ranka ir kitos rolÄ—s paliktos.{failure_text}"
        )
    )


@app_commands.command(
    name="ticket-add-member",
    description="Prideda Å¾mogÅ³ Ä¯ dabartinÄ¯ ticket kanalÄ…",
)
@app_commands.describe(member="Å½mogus, kurÄ¯ norite pridÄ—ti Ä¯ ticket")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def ticket_add_member(
    interaction: discord.Interaction, member: discord.Member
) -> None:
    is_ticket, is_owner, is_staff = ticket_access(interaction)
    if not is_ticket:
        await interaction.response.send_message(
            "Å iÄ… komandÄ… galima naudoti tik ticket kanale.", ephemeral=True
        )
        return
    if not is_owner and not is_staff:
        await interaction.response.send_message(
            "Å½mogÅ³ gali pridÄ—ti ticket autorius arba darbuotojas.", ephemeral=True
        )
        return
    channel = interaction.channel
    await channel.set_permissions(
        member,
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        attach_files=True,
        reason=f"Ä® ticket pridÄ—jo {interaction.user}",
    )
    await interaction.response.send_message(
        f"âœ… {member.mention} pridÄ—tas Ä¯ ticket."
    )


@app_commands.command(
    name="ticket-add-role",
    description="Prideda rolÄ™ Ä¯ dabartinÄ¯ ticket kanalÄ…",
)
@app_commands.describe(role="RolÄ—, kuriÄ… norite pridÄ—ti Ä¯ ticket")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def ticket_add_role(
    interaction: discord.Interaction, role: discord.Role
) -> None:
    is_ticket, _is_owner, is_staff = ticket_access(interaction)
    if not is_ticket:
        await interaction.response.send_message(
            "Å iÄ… komandÄ… galima naudoti tik ticket kanale.", ephemeral=True
        )
        return
    if not is_staff:
        await interaction.response.send_message(
            "RolÄ™ gali pridÄ—ti tik support darbuotojas arba kanalÅ³ valdytojas.",
            ephemeral=True,
        )
        return
    if interaction.guild is None or role == interaction.guild.default_role:
        await interaction.response.send_message(
            "Saugumo sumetimais @everyone rolÄ—s pridÄ—ti negalima.", ephemeral=True
        )
        return
    channel = interaction.channel
    await channel.set_permissions(
        role,
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        attach_files=True,
        reason=f"Ä® ticket rolÄ™ pridÄ—jo {interaction.user}",
    )
    await interaction.response.send_message(
        f"âœ… RolÄ— {role.mention} pridÄ—ta Ä¯ ticket.",
        allowed_mentions=discord.AllowedMentions(roles=False),
    )


@app_commands.command(
    name="setup-tickets",
    description="AutomatiÅ¡kai sukuria visÄ… ticket sistemÄ…",
)
@app_commands.describe(
    banner="Pagalbos centro bannerio paveikslÄ—lis",
    kanalas="Kanalas, kuriame paskelbti ticket lentele",
    kategorija="Kategorija, kurioje bus kuriami visi ticketai",
    support_role="DarbuotojÅ³ rolÄ—, kuri matys ir atsakys Ä¯ ticketus",
)
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def setup_tickets(
    interaction: discord.Interaction,
    banner: discord.Attachment,
    kanalas: discord.TextChannel,
    kategorija: discord.CategoryChannel,
    support_role: discord.Role,
) -> None:
    if not (
        interaction.permissions.manage_channels
        or interaction.permissions.manage_roles
        or interaction.permissions.administrator
    ):
        await interaction.response.send_message(
            "Å iai komandai reikia Manage Channels arba Manage Roles teisÄ—s.",
            ephemeral=True,
        )
        return
    if not banner.content_type or not banner.content_type.startswith("image/"):
        await interaction.response.send_message(
            "Banneris turi bÅ«ti paveikslÄ—lio failas.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    if guild is None or guild.me is None:
        await interaction.followup.send("Nepavyko rasti serverio informacijos.", ephemeral=True)
        return

    await interaction.followup.send(
        "⏳ Kuriu ticket sistemą... jeigu kažkas nepavyks, parašysiu klaidą čia.",
        ephemeral=True,
    )

    try:
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
        await kanalas.edit(
            overwrites=panel_overwrites,
            reason=f"Ticket sistema atnaujino {interaction.user}",
        )

        state["ticketConfigs"][str(guild.id)] = {
            "categoryId": str(kategorija.id),
            "panelChannelId": str(kanalas.id),
            "supportRoleId": str(support_role.id),
        }
        await save_state()
        panel = await send_ticket_panel(kanalas, banner)
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Nepavyko paruošti ticket sistemos, nes botui trūksta teisių. "
            "Duok botui `Manage Channels`, `Send Messages`, `Embed Links` ir `Attach Files`.",
            ephemeral=True,
        )
        return
    except discord.HTTPException as error:
        await interaction.followup.send(
            f"❌ Discord atmetė veiksmą: `{error}`\n"
            "Patikrink ar banneris nėra per didelis ir ar botas gali rašyti į pasirinktą kanalą.",
            ephemeral=True,
        )
        return
    except Exception as error:
        await interaction.followup.send(
            f"❌ Įvyko klaida setup metu: `{type(error).__name__}: {error}`",
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        f"✅ Ticket sistema paruošta: {panel.jump_url}\n"
        f"Kategorija: `{kategorija.name}` • Darbuotojai: {support_role.mention}",
        ephemeral=True,
    )


@app_commands.command(
    name="setup",
    description="AutomatiÅ¡kai sukuria visÄ… ticket sistemÄ…",
)
@app_commands.describe(
    support_role="DarbuotojÅ³ rolÄ—, kuri matys ir atsakys Ä¯ ticketus",
    banner="Pagalbos centro bannerio paveikslÄ—lis",
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
    description="IÅ¡siunÄia ticket sistemos panelÄ™ Ä¯ Å¡Ä¯ kanalÄ…",
)
@app_commands.describe(banner="Pagalbos centro bannerio paveikslÄ—lis")
@app_commands.default_permissions(manage_channels=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def ticket_panel(
    interaction: discord.Interaction, banner: discord.Attachment
) -> None:
    if not interaction.permissions.manage_channels:
        await interaction.response.send_message(
            "Å iai komandai reikia Manage Channels teisÄ—s.", ephemeral=True
        )
        return
    if not banner.content_type or not banner.content_type.startswith("image/"):
        await interaction.response.send_message(
            "Banneris turi bÅ«ti paveikslÄ—lio failas.", ephemeral=True
        )
        return
    if interaction.channel is None:
        return

    await interaction.response.defer(ephemeral=True)
    panel = await send_ticket_panel(interaction.channel, banner)
    await interaction.followup.send(
        f"Ticket panelÄ— sukurta: {panel.jump_url}", ephemeral=True
    )


@app_commands.command(
    name="disband", description="IÅ¡formuoja gaujÄ… ir uÅ¾deda 3 dienÅ³ cooldown"
)
@app_commands.describe(gauja="Gaujos rolÄ—, kurios narius reikia iÅ¡formuoti")
@app_commands.default_permissions(manage_roles=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def disband(interaction: discord.Interaction, gauja: discord.Role) -> None:
    await handle_disband(interaction, gauja)


@app_commands.command(
    name="disban", description="IÅ¡formuoja gaujÄ… ir uÅ¾deda 3 dienÅ³ cooldown"
)
@app_commands.describe(gauja="Gaujos rolÄ—, kurios narius reikia iÅ¡formuoti")
@app_commands.default_permissions(manage_roles=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def disban(interaction: discord.Interaction, gauja: discord.Role) -> None:
    await handle_disband(interaction, gauja)


def format_remaining(seconds: float) -> str:
    seconds = max(0, int(seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)


@app_commands.command(
    name="checkcd",
    description="Parodo aktyvius 3d cooldown narius ir likusi laika",
)
@app_commands.default_permissions(manage_roles=True)
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def checkcd(interaction: discord.Interaction) -> None:
    if not interaction.permissions.manage_roles:
        await interaction.response.send_message(
            "Siai komandai reikia Manage Roles teises.", ephemeral=True
        )
        return
    if interaction.guild is None:
        return

    await interaction.response.defer(ephemeral=True)
    now = time.time()
    lines = []
    cleaned = False
    for key, entry in list(state["cooldowns"].items()):
        guild_id_text, user_id_text = key.split(":")
        if int(guild_id_text) != interaction.guild.id:
            continue

        expires_at = float(entry["expiresAt"])
        if expires_at <= now:
            try:
                await expire_cooldown_now(interaction.guild.id, int(user_id_text), expires_at)
            except Exception as error:
                print(f"Checkcd: nepavyko nuimti pasibaigusio cooldown nuo {key}: {error}")
            cleaned = True
            continue

        member = interaction.guild.get_member(int(user_id_text))
        if member is None:
            try:
                member = await interaction.guild.fetch_member(int(user_id_text))
            except discord.NotFound:
                member = None
        if member:
            username = member.name
            if member.discriminator and member.discriminator != "0":
                username = f"{member.name}#{member.discriminator}"
            name = f"{member.display_name} (@{username}) - {member.mention}"
        else:
            name = f"Paliko serveri - ID {user_id_text}"
        lines.append(f"{name} - liko {format_remaining(expires_at - now)}")

    if cleaned:
        await save_state()

    embed = discord.Embed(
        title="Aktyvus 3d cooldown",
        color=discord.Color.orange(),
    )
    if lines:
        text = "\n".join(lines)
        if len(text) > 3900:
            kept = []
            total = 0
            for line in lines:
                if total + len(line) + 1 > 3800:
                    break
                kept.append(line)
                total += len(line) + 1
            text = "\n".join(kept)
            text += f"\n... ir dar {len(lines) - len(kept)} netilpo i lentele"
        embed.description = text
    else:
        embed.description = "Siuo metu aktyviu cooldown nariu nera."

    await interaction.followup.send(embed=embed, ephemeral=True)


@app_commands.command(
    name="iesko-nariu",
    description="Paskelbia gaujos nariu paieskos lentele",
)
@app_commands.describe(
    gaujos_pavadinimas="Gaujos pavadinimas",
    gaujos_spalva="Gaujos spalva",
    ieskoma_nariu="Kiek nariu ieskote",
    reikalavimai="Reikalavimai kandidatams",
    apie_gauja="Trumpas aprasymas ir kontaktas",
    galioja_iki="Iki kada galioja skelbimas, pvz. 2026-08-04",
)
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def iesko_nariu(
    interaction: discord.Interaction,
    gaujos_pavadinimas: str,
    gaujos_spalva: str,
    ieskoma_nariu: int,
    reikalavimai: str,
    apie_gauja: str,
    galioja_iki: str = "nenurodyta",
) -> None:
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        return
    if not member_has_boss_role(interaction.user) and not any(
        role_is_right_hand(role) for role in interaction.user.roles
    ):
        await interaction.response.send_message(
            "Sia komanda gali naudoti tik boso arba des.ranka role turintis narys.",
            ephemeral=True,
        )
        return

    channel = get_recruitment_channel(interaction.guild)
    if channel is None:
        await interaction.response.send_message(
            "Neradau RECRUITMENT_CHANNEL_ID kanalo. Patikrink Railway Variables.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(
        title="Gaujos iesko nariu!",
        color=discord.Color.green(),
    )
    embed.set_author(
        name=interaction.user.display_name,
        icon_url=interaction.user.display_avatar.url,
    )
    embed.add_field(name="Gaujos pavadinimas", value=gaujos_pavadinimas, inline=True)
    embed.add_field(name="Bosas", value=interaction.user.mention, inline=True)
    embed.add_field(name="Gauju spalva", value=gaujos_spalva, inline=True)
    embed.add_field(
        name="Ieskoma nariu skaicius",
        value=f"mes turim {ieskoma_nariu}",
        inline=False,
    )
    embed.add_field(name="Reikalavimai", value=reikalavimai, inline=False)
    embed.add_field(name="Apie gauja ir kontaktas", value=apie_gauja, inline=False)
    embed.set_footer(
        text=(
            f"Skelbimas galioja iki {galioja_iki} â€¢ "
            f"Paskelbe: {interaction.user.display_name}"
        )
    )

    sent = await channel.send(embed=embed)
    await interaction.followup.send(
        f"Skelbimas paskelbtas: {sent.jump_url}",
        ephemeral=True,
    )


bot.tree.add_command(setup_tickets)
bot.tree.add_command(pakeisti_spalva)
bot.tree.add_command(checkcd)
bot.tree.add_command(iesko_nariu)
bot.tree.add_command(disband)
bot.run(TOKEN)
