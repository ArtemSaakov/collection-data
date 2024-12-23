# script for fetching LoC data for assignment 1.
# at the moment, this is tuned for the LoC free-to-use collection library set.
# the script fetches overarching set info, creates a setlist of the items as a csv file, fetches metadata
# for each item in the setlist, and then fetches the large image for each item.
import requests as req
import json
from pathlib import Path
import csv


LOC_ROOT = "https://loc.gov/"
LCCN_ROOT = "https://lccn.loc.gov/"
SEARCH_ROOT = "https://www.loc.gov/search"
COLLECTION_DATA_DIR = Path(__file__).resolve().parent
METADATA_DIR = (COLLECTION_DATA_DIR / Path("item-metadata")).resolve()
ITEM_DIR = (COLLECTION_DATA_DIR / Path("item-files")).resolve()


def fetch_loc_url(url: str, root: str = None, json_opt: bool = False) -> req.Response | None:
    """
    Fetches an LOC url; handles it based on if JSON is in the url.

    Args:
        url (str): The URL to fetch. If root is provided, it will be treated as an endpoint to the root.
        params (dict, optional): A dictionary of query string parameters to send with the request. Defaults to None.
        root (str, optional): A root URL to prepend to the URL. Defaults to None.

    Raises:
        Exception: If there is an error fetching the URL, it will be caught and printed.

    Returns:
        req.Response | None: The HTTP response object, or None if there is an error.
    """
    if root:
        url = f"{root.rstrip('/')}/{url.lstrip('/')}"

    try:
        if json_opt:
            resp = req.get(url=url, params={"fo": "json"})
            if resp.status_code == 200 and 'json' in resp.headers.get('content-type').lower():
                return resp
            print(f"Error: status code is not 200 or content type is not JSON.")
        else:
            resp = req.get(url=url)
            if resp.status_code == 200:
                return resp
            print(f"Error: status code is not 200.")
    except Exception as e:
        print(f"Error for {url}: {e}")


def save_to_file(res: req.Response, filename: str, dir_path: Path = None) -> bool | None:
    """
    Saves the content of an HTTP response to a file.

    Works to anticipate json, jpeg/jpg, or text file types.

    Args:
        res (req.Response): The HTTP response object containing the content to save.
        filename (str): The base name of the file to save the content to, without an extension.
        dir_path (Path, optional): The directory path to save the file to. Defaults to None.

    Raises:
        Exception: If there is an error during the file writing process.

    Returns:
        bool | None: True if file written successfully, None if otherwise.
    """

    try:
        content_type = res.headers.get('content-type').lower()
        def _check_file_exist(file):
            if file.is_file():
                print(f"File {file} already exists.")
                return True

        if 'json' in content_type:
            filename = dir_path / Path(f'{filename}.json') if dir_path else Path(f'{filename}.json')
            if _check_file_exist(filename):
                return
            with open(filename, "w", encoding='utf-8') as f:
                json.dump(res.json(), f, ensure_ascii=False, indent=2)

        elif 'text' in content_type:
            filename = dir_path / Path(f'{filename}.txt') if dir_path else Path(f'{filename}.txt')
            if _check_file_exist(filename):
                return
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(res.text)

        elif 'jpeg' in content_type or 'jpg' in content_type:
            filename = dir_path / Path(f'{filename}.jpg') if dir_path else Path(f'{filename}.jpg')
            if _check_file_exist(filename):
                return
            with open(filename, 'wb') as f:
                f.write(res.content)

        else:
            print(f"Unsupported content type: {content_type}")
            return
        print(f"File has been written to {dir_path} as {filename}")
        return True

    except Exception as e:
        print(f'Error writing file: {e}')



def dicts_to_csv(list_input: list, filename: str, dir_path: Path = None) -> bool | None:
    """
    Converts a list of dictionaries to a csv file.

    Args:
        list_input (list): A list of dictionaries where each dictionary represents a row in the csv file.
        filename (str): The name of the csv file to be created.
        dir_path (Path, optional): The directory path where the csv file will be saved. Defaults to None.

    Returns:
        bool | None: Returns True if the file was written successfully, otherwise returns None.

    Raises:
        Exception: If there is an error while writing the file, an exception is caught and an error message is printed.
    """

    filename = dir_path / Path(filename) if dir_path else Path(filename)

    try:
        with open(filename, "w", encoding="utf-8") as f:
            csv_writer = csv.DictWriter(f, fieldnames=list_input[0].keys())
            csv_writer.writeheader()
            for row in list_input:
                csv_writer.writerow({h:i.strip() for h, i in row.items()})
        print(f"File has been written to {dir_path} as {filename}")
        return True
    except Exception as e:
        print(f"Error saving file: {e}")


def metadata_from_csv(filename: str, filename_dir: Path, metadata_dir: Path = None) -> tuple:
    """
    Extracts metadata from a csv file and saves it to a specified directory.

    Args:
        filename (str): The name of the csv file containing metadata links.
        filename_dir (Path): The directory path where the csv file is located.
        metadata_dir (Path, optional): The directory path where the metadata files will be saved. Defaults to None.

    Returns:
        tuple: A tuple containing three integers:
            - metadata_success (int): The number of successfully fetched and saved metadata entries.
            - metadata_fetch_error (int): The number of errors encountered while fetching metadata.
            - metadata_save_error (int): The number of errors encountered while saving metadata.
    """
    metadata_success, metadata_fetch_error, metadata_save_error = 0, 0, 0
    filename = filename_dir / Path(filename)

    try:
        with open(filename, "r", encoding="utf-8") as f:
            csv_reader = csv.DictReader(f)
            for i in csv_reader:
                metadata = fetch_loc_url(url=i['link'], root=LOC_ROOT, json_opt=True)
                if not metadata:
                    metadata_fetch_error += 1
                    print(f"Error fetching metadata for {i['link']}")
                else:
                    item = metadata.json().get("item", {})
                    id = item['item'].get('control_number') or item.get("id", '').split('/')[-2] or item.get('url', '').split('/')[-2]

                    if not save_to_file(metadata, f'cn_{id}', dir_path=metadata_dir):
                        metadata_save_error += 1
                    else:
                        metadata_success += 1
    except Exception as e:
        print(f"Error reading collection file: {e}")
    return metadata_success, metadata_fetch_error, metadata_save_error


def load_json_metadata(file: Path) -> dict:
    """
    Load metadata from a json file and extract specific fields.

    Args:
        file (Path): A file containing metadata.

    Returns:
        dict: A dictionary containing extracted metadata fields:
            - 'item_URI': The URI of the item.
            - 'lccn': The Library of Congress Control Number.
            - 'title': The title of the item.
            - 'image_URL_large': The URL of the large image.

    If an error occurs during extraction, the dictionary will contain the error message.

    Raises:
        Exception: If there is an issue opening or reading the file.
    """
    try:
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f).get('item', {})
            return {
                'item_URI': data.get('id'),
                'lccn': data.get('library_of_congress_control_number') or data.get('control_number'),
                'title': data.get('title'),
                'image_URL_large': data.get('image_url')[-1],
            }

    except Exception as e:
        print(f"Error loading metadata from {file}: {e}")
        return {file: {"error": e}}


def files_from_list(file_list: list, dir_path: Path = None) -> tuple:
    """
    Processes a list of files, fetching images from urls and saving them to a specified directory.

    Args:
        file_list (list): A list of dictionaries, each containing 'image_URL_large' and either 'lccn' or 'cn'.
        dir_path (Path, optional): The directory path where files will be saved. Defaults to None.

    Returns:
        tuple: A tuple containing the counts of items processed, files saved, and errors encountered.
    """
    items, files, errors = 0, 0, 0
    for i in file_list:
        url = i.get('image_URL_large')
        id = i.get('item_URI').split('/')[-2] if i.get('item_URI') else i.get('lccn')
        print(f"Fetching image URL for {url}...\n")
        r = fetch_loc_url(url=url)
        items += 1
        if r and id and url:
            if save_to_file(r, f"img_{id}", dir_path=dir_path):
                files += 1
            else:
                errors += 1
        else:
            print(f"Error fetching image for ID {id}, url {url}")
            errors += 1
    return items, files, errors

def main():

    set_name = 'glasses'

    for i in [METADATA_DIR, ITEM_DIR]:
        try:
            i.mkdir()
            print(f"Directory '{i}' created successfully.")
        except FileExistsError:
            print(f"Directory '{i}' already exists.")

    print(f"Fetching free-to-use {set_name} set JSON info...\n")

    set_info = fetch_loc_url(f"https://www.loc.gov/free-to-use/{set_name}/", json_opt=True)

    print(f"Saving set info JSON as ftu-{set_name}-set-info.json...\n")

    save_to_file(set_info, f"ftu-{set_name}-set-info", dir_path=COLLECTION_DATA_DIR)
    content = set_info.json().get("content", {})
    set_info = content.get("set", {})
    final_set_list = set_info.get("items", [])

    print(f"\nWriting set_info list to CSV as ftu-{set_name}-set-list.csv...")
    if not dicts_to_csv(final_set_list, f"ftu-{set_name}-set-list.csv", dir_path=COLLECTION_DATA_DIR):
        raise Exception("Error writing to CSV.")

    print(f"\nFetching metadata from ftu-{set_name}-set-list.csv...\n")

    metadata_files_collected_successfully, metadata_fetch_errors, metadata_filesave_errors = metadata_from_csv(f"ftu-{set_name}-set-list.csv", COLLECTION_DATA_DIR, metadata_dir=METADATA_DIR)

    print(f"\nNumber of items in collection list: {len(final_set_list)}")
    print(f"Metadata files collected successfully: {metadata_files_collected_successfully}")
    print(f"Errors related to fetching metadata from API: {metadata_fetch_errors}")
    print(f"Errors related to writing metadata to file: {metadata_filesave_errors}")

    metadata_files = list(METADATA_DIR.glob("*.json"))

    print(f"\nFetching image urls from recorded metadata for {len(metadata_files)} items...\n")

    images_set_list = [load_json_metadata(i) for i in metadata_files]

    print("Writing images to item-files directory...\n")

    item_count, file_count, error_count = files_from_list(images_set_list, dir_path=ITEM_DIR)

    print(f"Number of images fetched from metadata list: {len(images_set_list)}")
    print(f"Number of items fetched successfully: {item_count}")
    print(f"Number of jpg files written successfully: {file_count}")
    print(f"Number of errors encountered: {error_count}")


if __name__ == "__main__":
    main()
