# tool for creating a csv file from LoC metadata for ingestion into Omeka S
# via the CSV Import module.
# compliments, and is complimented by, collection-extract-tools.py.
# desgined in accordance with the Metadata Application Profile for the Library of
# Congress Free-to-Use: Libraries set.

from datetime import date, datetime
import re
import html
import csv
import json
from pathlib import Path

METADATA = (Path(__file__).parent / Path("item-metadata")).resolve()

if not METADATA.exists():
    raise FileNotFoundError(f"Metadata path does not exist: {METADATA}")


def month_name_to_number(month_name):
    """
    Convert a month name to its corresponding month number.
    Could potentially be done with the datetime module, but this provides more
    granular control.

    Args:
        month_name (str): The name of the month (e.g., "Jan", "Jan.", "January").

    Returns:
        int: The month number (1-12) or None if not recognized.
    """
    # Normalize month name
    month_name = month_name.strip(".").lower()
    month_map = {
        "jan": 1,
        "jan.": 1,
        "january": 1,
        "feb": 2,
        "feb.": 2,
        "february": 2,
        "mar": 3,
        "mar.": 3,
        "march": 3,
        "apr": 4,
        "apr.": 4,
        "april": 4,
        "may": 5,
        "jun": 6,
        "jun.": 6,
        "june": 6,
        "jul": 7,
        "jul.": 7,
        "july": 7,
        "aug": 8,
        "aug.": 8,
        "august": 8,
        "sep": 9,
        "sep.": 9,
        "sept": 9,
        "sept.": 9,
        "september": 9,
        "oct": 10,
        "oct.": 10,
        "october": 10,
        "nov": 11,
        "nov.": 11,
        "november": 11,
        "dec": 12,
        "dec.": 12,
        "december": 12,
    }
    return month_map.get(month_name, None)


def extract_dates(container: list) -> str:
    """
    Extracts and formats dates from a given list of strings or lists of strings.

    Args:
        container (list): A list containing strings or a list from which dates are to be extracted.

    Returns:
        str: A formatted date string in one of the following formats:
             - "yyyy-mm-dd" for full dates
             - "yyyy-mm" for year and month
             - "yyyy/yyyy" for year ranges
             - "yyyy" for single years
             - An empty string if no recognizable date is found
    """

    # if container contains a nested list, extract the first item from the
    # nested list, as that is the portion that contains date values for these
    # instances
    text = (
        [i for i in container if isinstance(i, list)][0][0]
        if len(container) > 1
        else container[0]
    )

    clean_text = re.sub(r"\[|\]|\(|\)|\?|ca\.?|c\.?", "", text.lower())
    clean_text = clean_text.strip()

    # full date patterns (yyyy-mm-dd or variants)
    # this will match formats like: "2015-09-30", "2015/09/30", "2015.09.30", which
    # may be unnecessary for this set, but is good practice nonetheless
    full_date_pattern = re.compile(
        r"(?P<year>\d{4})[\./\- ](?P<month>\d{1,2})[\./\- ](?P<day>\d{1,2})"
    )
    m = full_date_pattern.search(clean_text)
    if m:
        year = int(m.group("year"))
        month = int(m.group("month"))
        day = int(m.group("day"))
        # just assume correctness and format it
        return f"{year:04d}-{month:02d}-{day:02d}"

    # year range: "between 1900 and 1905" or "1900-1905" or "1900 and 1905"
    year_range_pattern = re.compile(r"(?:between\s+)?(\d{4})\D+(?:and|-|to)\D+(\d{4})")
    yr_range = year_range_pattern.search(clean_text)
    if yr_range:
        y1 = int(yr_range.group(1))
        y2 = int(yr_range.group(2))
        # return "yyyy/yyyy"
        return f"{y1:04d}/{y2:04d}"

    # year-month (like "sept 1941", "1941 sept", "2012 september")
    # we'll try obth "year month" and "month year"
    ym_pattern = re.compile(
        r"(?P<year>\d{4})[\s.,]*(?P<monthname>[a-zA-Z]+)|(?P<monthname2>[a-zA-Z]+)[\s.,]*(?P<year2>\d{4})"
    )
    ym = ym_pattern.search(clean_text)
    if ym:
        if ym.group("year") and ym.group("monthname"):
            year = int(ym.group("year"))
            month_str = ym.group("monthname")
        else:
            year = int(ym.group("year2"))
            month_str = ym.group("monthname2")

        month_num = month_name_to_number(month_str)
        if month_num:
            # return yyyy-mm
            return f"{year:04d}-{month_num:02d}"
        else:
            # if month not recognized, just return the year
            return f"{year:04d}"

    # single year
    year_pattern = re.compile(r"(\d{4})")
    y = year_pattern.search(clean_text)
    if y:
        year = int(y.group(1))
        return f"{year:04d}"

    # if no recognizable date found
    return ""


def extract_description(desc: str, notes: list) -> str:
    """
    Extracts a description from `desc`. If a match is found using the regex pattern below,
    the matched group is returned. If no match is found, returns the joined `notes`.

    Args:
        desc (str): The description string.
        notes (list): The notes container.

    Returns:
        str: The extracted description or the joined `notes` string.
    """
    match = re.search(r"\. \| (.+)", desc)
    if not match:
        return " ".join(notes)
    return match.group(1)


def determine_extent_form(container: list) -> str | tuple:
    """
    Determines the physical extent and physical form from a container list.

    Args:
        container (list): List of extent and form descriptions.

    Returns:
        str | tuple:
            - Tuple with joined items and empty string if container has multiple items.
            - Tuple with extent and form extracted using regex if single item has both colon and semicolon.
            - Tuple with extent and form split by colon if single item has a colon.
            - Tuple with single item and an empty string otherwise.

    """

    # I'd like to note here at least one item this function doesn't account for,
    # resulting in an instance of the Physical Form being conjoined
    # with the Physical Extent. this could be resolved, but in lieu of
    # a consistent sleep schedule or an excessive amount of other instances of this issue
    # arising , I chose to leave it be
    if len(container) > 1:
        return ("|".join(i.strip() for i in container), "")

    if ":" in container[0] and ";" in container[0]:
        # regex pattern to extract text before colon, between colon and
        # semicolon, and aftr semicolon
        match = re.match(r"^(.*?)\s*:\s*(.*?)\s*;\s*(.*)$", container[0])
        extent1, form, extent2 = match.group(1), match.group(2), match.group(3)
        return ("|".join([extent1.strip(), extent2.strip()]), form.strip())
    elif ":" in container[0]:
        extent, form = container[0].split(" : ")
        return (extent.strip(), form.strip())
    else:
        return (container[0].strip(), "")


def clean_html_text(html_text: list) -> str:
    """
    Cleans the provided HTML text by performing the following steps:
    1. Removes HTML tags.
    2. Decodes HTML escape sequences (e.g., &nbsp;) to their corresponding characters.
    3. Replaces multiple spaces, tabs, and newlines with a single space.
    Args:
        html_text (str): The HTML text to be cleaned.
    Returns:
        str: The cleaned text with HTML tags removed, escape sequences decoded,
             and extraneous whitespace characters replaced by a single space.
    """
    if not html_text:
        return ""
    # remove HTML tags
    no_tags = re.sub(r"<[^>]+>", " ", html_text[0])

    # decode HTML escape sequences (&nbsp; etc) to a space
    decoded_text = html.unescape(no_tags)

    # Step 3: Replace multiple spaces, tabs, and newlines with a single space
    cleaned_text = re.sub(r"\s+", " ", decoded_text).strip()

    return cleaned_text


def main() -> None:
    data_list = []
    td = date.today().strftime("%Y-%m-%d")
    file_open_error = 0
    dc = "dcterms:"
    mods = "mods:"

    for i in METADATA.iterdir():
        try:
            f = i.read_text(encoding="utf-8")
            data = json.loads(f).get("item", {})
            deep_data = data.get("item", {})
            data_dict = {}
            if data:
                data_dict["item_type"] = "Item"
                data_dict["date_uploaded"] = td
                data_dict["source_file"] = f'../{"/".join(i.parts[-3:])}'
                data_dict[f"{dc}title"] = data.get("title", "")
                data_dict[f"{dc}created"] = extract_dates(
                    data.get("created_published", [""])
                )
                data_dict[f"{dc}description"] = extract_description(
                    data.get("description", [""])[0], data.get("notes", [""])
                )
                data_dict[f"{dc}contributor"] = "|".join(
                    data.get("contributor_names", [""])
                )
                data_dict[f"{dc}identifier:controlNumber"] = deep_data.get(
                    "control_number"
                ) or data.get("library_of_congress_control_number", "")
                data_dict[f"{mods}locationUrl"] = data.get("link", "")
                data_dict[f"{mods}mediaType"] = "|".join(data.get("mime_type", [""]))
                ext_form = determine_extent_form(data.get("medium", [""]))
                data_dict[f"{mods}physicalExtent"] = ext_form[0]
                data_dict[f"{mods}physicalForm"] = ext_form[1]
                data_dict[f"{dc}subject"] = "|".join(
                    i.strip() for i in data.get("subject_headings", [""])
                )
                data_dict[f"{dc}language"] = data.get("language", [""])[0]
                # populates Access Condition based on either availability
                # of the attributes specified below
                data_dict[f"{mods}accessCondition"] = data.get(
                    "rights_advisory"
                ) or data.get("rights_information", "")
                data_dict[f"{dc}rights"] = clean_html_text(
                    data.get(
                        "rights",
                        [],
                    )
                ) or "See Access Condition or item source for rights information."
            else:
                print(f"No data from {str(i)}:(")
            data_list.append(data_dict)
        except Exception as e:
            print(f"Error opening {i}: {e}")
            file_open_error += 1
    print(f"\nErrors opening files: {file_open_error}\n")
    try:
        with open(
            f"{Path(__file__).parent}/omeka-ingest-data.csv", "w", encoding="utf-8"
        ) as f:
            writer = csv.DictWriter(f, fieldnames=data_list[0].keys())
            writer.writeheader()
            for row in data_list:
                writer.writerow(row)
        print(
            f"File has been written to {Path(__file__).parent} as {'omeka-ingest-data.csv'}"
        )
        return
    except Exception as e:
        print(f"Error saving file: {e}")


if __name__ == "__main__":
    main()
