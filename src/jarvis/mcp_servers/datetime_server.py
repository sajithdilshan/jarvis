"""Lightweight MCP server for date, time, and day of week.
Copied from: https://github.com/cfdude/mcp-datetimeday/tree/main

Copyright (c) 2026 cfdude

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import argparse
from calendar import monthrange
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mcp-datetimeday")


@mcp.tool()
def get_datetime(
    tz: str | None = None,
    format: str | None = None,
) -> dict:
    """
    Get current date and time with day of week.

    Args:
        tz: IANA timezone (e.g., "America/New_York", "UTC"). Defaults to local.
        format: Output format - "iso8601", "unix", "human", or None for full response.

    Returns:
        Formatted datetime with day of week always included.
    """
    if tz:
        try:
            zone = ZoneInfo(tz) if tz != "UTC" else timezone.utc
            now = datetime.now(zone)
        except Exception:
            return {"error": f"Invalid timezone: {tz}"}
    else:
        now = datetime.now().astimezone()

    day_of_week = now.strftime("%A")

    if format == "iso8601":
        return {"day_of_week": day_of_week, "iso8601": now.isoformat()}
    elif format == "unix":
        return {"day_of_week": day_of_week, "unix_timestamp": int(now.timestamp())}
    elif format == "human":
        return {
            "day_of_week": day_of_week,
            "human_readable": now.strftime("%A, %B %d, %Y at %I:%M %p"),
        }

    # Default: full response
    return {
        "day_of_week": day_of_week,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "timezone": str(now.tzinfo),
        "utc_offset": now.strftime("%z"),
        "iso8601": now.isoformat(),
        "unix_timestamp": int(now.timestamp()),
        "human_readable": now.strftime("%A, %B %d, %Y at %I:%M %p"),
    }


@mcp.tool()
def relative_time(date_str: str, reference: str | None = None) -> dict:
    """
    Get relative time description between two dates.

    Args:
        date_str: Target date in YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS format.
        reference: Reference date (same formats). Defaults to now.

    Returns:
        Relative time description (e.g., "3 days ago", "in 2 weeks").
    """
    formats = ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]

    target = None
    for fmt in formats:
        try:
            target = datetime.strptime(date_str, fmt)
            break
        except ValueError:
            continue

    if not target:
        return {"error": f"Invalid date format: {date_str}. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS."}

    if reference:
        ref = None
        for fmt in formats:
            try:
                ref = datetime.strptime(reference, fmt)
                break
            except ValueError:
                continue
        if not ref:
            return {"error": f"Invalid reference date format: {reference}"}
    else:
        ref = datetime.now()

    delta = target - ref
    total_seconds = delta.total_seconds()
    is_future = total_seconds > 0
    abs_seconds = abs(total_seconds)

    days = int(abs_seconds // 86400)
    hours = int((abs_seconds % 86400) // 3600)
    minutes = int((abs_seconds % 3600) // 60)
    seconds = int(abs_seconds % 60)

    if days >= 365:
        years = days // 365
        unit = "year" if years == 1 else "years"
        desc = f"{years} {unit}"
    elif days >= 30:
        months = days // 30
        unit = "month" if months == 1 else "months"
        desc = f"{months} {unit}"
    elif days >= 7:
        weeks = days // 7
        unit = "week" if weeks == 1 else "weeks"
        desc = f"{weeks} {unit}"
    elif days > 0:
        unit = "day" if days == 1 else "days"
        desc = f"{days} {unit}"
    elif hours > 0:
        unit = "hour" if hours == 1 else "hours"
        desc = f"{hours} {unit}"
    elif minutes > 0:
        unit = "minute" if minutes == 1 else "minutes"
        desc = f"{minutes} {unit}"
    else:
        unit = "second" if seconds == 1 else "seconds"
        desc = f"{seconds} {unit}"

    relative = f"in {desc}" if is_future else f"{desc} ago"
    if abs_seconds < 1:
        relative = "now"

    return {
        "target": date_str,
        "target_day_of_week": target.strftime("%A"),
        "reference": reference or "now",
        "relative": relative,
        "days_difference": delta.days,
        "total_seconds": int(total_seconds),
    }


@mcp.tool()
def days_in_month(year: int | None = None, month: int | None = None) -> dict:
    """
    Get the number of days in a month.

    Args:
        year: Year (e.g., 2025). Defaults to current year.
        month: Month (1-12). Defaults to current month.

    Returns:
        Number of days in the month, plus first/last day info.
    """
    now = datetime.now()
    year = year or now.year
    month = month or now.month

    if not 1 <= month <= 12:
        return {"error": f"Invalid month: {month}. Must be 1-12."}

    first_weekday, num_days = monthrange(year, month)
    first_day = datetime(year, month, 1)
    last_day = datetime(year, month, num_days)

    return {
        "year": year,
        "month": month,
        "month_name": first_day.strftime("%B"),
        "days_in_month": num_days,
        "first_day": {
            "date": first_day.strftime("%Y-%m-%d"),
            "day_of_week": first_day.strftime("%A"),
        },
        "last_day": {
            "date": last_day.strftime("%Y-%m-%d"),
            "day_of_week": last_day.strftime("%A"),
        },
        "is_leap_year": year % 4 == 0 and (year % 100 != 0 or year % 400 == 0),
    }


@mcp.tool()
def convert_time(
    time_str: str,
    from_tz: str,
    to_tz: str,
) -> dict:
    """
    Convert time between timezones.

    Args:
        time_str: Time in YYYY-MM-DD HH:MM:SS or YYYY-MM-DDTHH:MM:SS format.
        from_tz: Source IANA timezone (e.g., "America/New_York", "UTC").
        to_tz: Target IANA timezone.

    Returns:
        Converted time with day of week for both timezones.
    """
    formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]

    dt = None
    for fmt in formats:
        try:
            dt = datetime.strptime(time_str, fmt)
            break
        except ValueError:
            continue

    if not dt:
        return {"error": f"Invalid time format: {time_str}"}

    try:
        source_zone = ZoneInfo(from_tz) if from_tz != "UTC" else timezone.utc
        target_zone = ZoneInfo(to_tz) if to_tz != "UTC" else timezone.utc
    except Exception as e:
        return {"error": f"Invalid timezone: {e}"}

    source_dt = dt.replace(tzinfo=source_zone)
    target_dt = source_dt.astimezone(target_zone)

    return {
        "from": {
            "day_of_week": source_dt.strftime("%A"),
            "datetime": source_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": from_tz,
            "utc_offset": source_dt.strftime("%z"),
        },
        "to": {
            "day_of_week": target_dt.strftime("%A"),
            "datetime": target_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": to_tz,
            "utc_offset": target_dt.strftime("%z"),
        },
    }


@mcp.tool()
def get_week_year(date_str: str | None = None) -> dict:
    """
    Get week number and ISO week of the year.

    Args:
        date_str: Date in YYYY-MM-DD format. Defaults to today.

    Returns:
        Week number, ISO week, day of year, and related info.
    """
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return {"error": f"Invalid date format: {date_str}. Use YYYY-MM-DD."}
    else:
        dt = datetime.now()

    iso_cal = dt.isocalendar()

    return {
        "date": dt.strftime("%Y-%m-%d"),
        "day_of_week": dt.strftime("%A"),
        "day_of_week_number": dt.isoweekday(),
        "week_number": (dt.timetuple().tm_yday - 1) // 7 + 1,
        "iso_week": iso_cal[1],
        "iso_year": iso_cal[0],
        "day_of_year": dt.timetuple().tm_yday,
        "days_remaining_in_year": (datetime(dt.year, 12, 31) - dt).days,
        "is_weekend": dt.isoweekday() >= 6,
        "quarter": (dt.month - 1) // 3 + 1,
    }


@mcp.tool()
def get_current_time(tz: str | None = None, format: str | None = None) -> dict:
    """
    Alias for get_datetime — current date and time with day of week.

    Args:
        tz: IANA timezone (e.g., "America/New_York", "UTC"). Defaults to local.
        format: Output format - "iso8601", "unix", "human", or None for full response.
    """
    return get_datetime(tz=tz, format=format)


def main():
    """Run the MCP server."""
    parser = argparse.ArgumentParser(description="mcp-datetimeday MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8105,
        help="Port for HTTP transport (default: 8105)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for HTTP transport (default: 127.0.0.1)",
    )
    args = parser.parse_args()

    if args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
