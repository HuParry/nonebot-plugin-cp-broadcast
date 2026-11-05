"""Render Codeforces profile cards locally, without remote images or a browser."""

from io import BytesIO
from datetime import datetime, timedelta, timezone


RANK_COLORS = {
    "newbie": "#808080", "pupil": "#008000", "specialist": "#03A89E",
    "expert": "#0000FF", "candidate master": "#AA00AA",
    "master": "#FF8C00", "international master": "#FF8C00",
    "grandmaster": "#FF0000", "international grandmaster": "#FF0000",
    "legendary grandmaster": "#FF0000",
}


def _number(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def format_last_online(value):
    """Format a Unix timestamp in UTC+8, independently of the bot's OS timezone."""
    timestamp = _number(value)
    if timestamp is None:
        return "-"
    try:
        return datetime.fromtimestamp(timestamp, timezone(timedelta(hours=8))).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except (ValueError, OverflowError, OSError):
        return "-"


def render_user_card(profile, avatar=None, preview=False):
    """Return one RGB PNG. All displayed statistics come from user.info."""
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    portrait = None
    if avatar:
        try:
            with Image.open(BytesIO(avatar)) as source:
                if source.width * source.height > 4000000:
                    raise ValueError("Avatar resolution is too large")
                portrait = ImageOps.fit(
                    ImageOps.exif_transpose(source).convert("RGB"), (104, 104),
                    method=Image.Resampling.LANCZOS,
                )
        except (OSError, ValueError, Image.DecompressionBombError):
            # Invalid avatar bytes must not prevent rendering the actual data.
            portrait = None

    image = Image.new("RGB", (960, 340), "#F2F4F7")
    draw = ImageDraw.Draw(image)
    fonts = {}

    def text(position, value, size=22, color="#202D3D", bold=False,
             max_width=None, min_size=None):
        value = str(value)
        # Pillow ships a scalable font; no OS fonts need to be installed.
        while True:
            if size not in fonts:
                fonts[size] = ImageFont.load_default(size=size)
            font = fonts[size]
            if (max_width is None or min_size is None or size <= min_size or
                    draw.textlength(value, font=font) <= max_width):
                break
            size -= 1
        if max_width is not None:
            original = value
            while value and draw.textlength(value, font=font) > max_width:
                value = value[:-1]
            if value != original:
                value = value[:-3] + "..." if len(value) > 3 else "..."
        draw.text(position, value, font=font, fill=color,
                  stroke_width=1 if bold else 0, stroke_fill=color)

    handle = str(profile.get("handle") or "Unknown")
    rating = _number(profile.get("rating"))
    max_rating = _number(profile.get("maxRating"))
    rank = str(profile.get("rank") or "Unrated")
    rank_color = RANK_COLORS.get(rank.lower(), "#808080")
    peak_rank = str(profile.get("maxRank") or "Unrated")
    contribution = _number(profile.get("contribution"))
    last_online = format_last_online(profile.get("lastOnlineTimeSeconds"))

    draw.rounded_rectangle((16, 12, 944, 328), radius=16, fill="white", outline="#DCE2EA")

    # Codeforces' familiar red / yellow / blue mark and blue section borders.
    for x, y, color in ((48, 43, "#E8554E"), (61, 32, "#F4C542"), (74, 38, "#3684CA")):
        draw.rounded_rectangle((x, y, x + 8, 61), radius=2, fill=color)
    text((94, 33), "Codeforces", 25, "#285C98", bold=True)
    if preview:
        text((790, 39), "SAMPLE DATA", 13, "#8795A6")

    name_x, name_width = 46, 620
    if portrait is not None:
        mask = Image.new("L", (104, 104), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, 103, 103), radius=12, fill=255)
        draw.rounded_rectangle((46, 82, 154, 190), radius=14, outline="#DCE5EE", width=2)
        image.paste(portrait, (48, 84), mask)
        name_x, name_width = 178, 488
    text((name_x, 84), handle, 54, rank_color, bold=True, max_width=name_width, min_size=26)
    text((name_x + 3, 151), rank, 25, rank_color, max_width=name_width)
    draw.line((700, 88, 700, 178), fill="#E1E8F0", width=2)
    text((733, 79), rating if rating is not None else "Unrated",
         72 if rating is not None else 42, rank_color, bold=True)
    text((738, 159), "Rating", 20, "#6A7C92")

    draw.line((48, 201, 912, 201), fill="#DCE5EE", width=2)
    stats = (
        (48, "Max rating", str(max_rating) if max_rating is not None else "-",
         RANK_COLORS.get(peak_rank.lower(), "#808080")),
        (348, "Contribution", "{:+d}".format(contribution) if contribution is not None else "-",
         "#25804D" if contribution is not None and contribution >= 0 else "#B44444"),
    )
    for x, label, value, color in stats:
        text((x, 222), label, 21, "#718299")
        text((x - 1, 252), value, 45, color, bold=True, max_width=260)
    text((648, 222), "Last Online", 21, "#718299")
    text((808, 227), "UTC+8", 14, "#8795A6")
    date, _, clock = last_online.partition(" ")
    text((648, 253), date, 28, "#285C98")
    if clock:
        text((648, 286), clock, 25, "#285C98")
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
