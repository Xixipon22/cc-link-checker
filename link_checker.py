import argparse
import sys
from urllib.parse import urlsplit, urljoin

import requests
from bs4 import BeautifulSoup

# Set defaults
err_code = 0
verbose = False
output_err = False
header = {
    "User-Agent": "Mozilla/5.0 (X11; Linux i686 on x86_64; rv:10.0) Gecko/20100101 Firefox/10.0"
}
scraped_links = {}


parser = argparse.ArgumentParser(description="Script to check broken links")
parser.add_argument(
    "-v", "--verbose", help="Increase verbosity of output", action="store_true"
)
parser.add_argument(
    "--output-error",
    help="Outputs all link errors to file (default: errorlog.txt)",
    metavar="output_file",
    const="errorlog.txt",
    nargs="?",
    type=argparse.FileType("w", encoding="utf-8"),
    dest="output",
)
args = parser.parse_args()
if args.verbose:
    verbose = True
if args.output:
    output = args.output
    output_err = True


def get_all_license():
    """This function scrapes all the license file in the repo 'https://github.com/creativecommons/creativecommons.org/tree/master/docroot/legalcode'.

    Returns:
        str[]: The list of license/deeds files found in the repository
    """
    url = "https://github.com/creativecommons/creativecommons.org/tree/master/docroot/legalcode"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "lxml")
    links = soup.table.tbody.find_all("a", class_="js-navigation-open")
    print("No. of files to be checked:", len(links))
    return links


def create_absolute_link(link_analysis, href):
    if (
        link_analysis.scheme == ""
        and link_analysis.netloc == ""
        and link_analysis.path != ""
    ):
        href = urljoin(base_url, href)
    return href


def check_existing(link, base_url):
    """This function checks if the link is already present in scraped_links.

    Args:
        link (bs4.element.Tag): The anchor tag extracted using BeautifulSoup which is to be checked

    Returns:
        String or Number: The status of the link
    """
    href = link["href"]
    analyse = urlsplit(href)
    href = create_absolute_link(analyse, href)
    status = scraped_links.get(href)
    if status:
        return status
    else:
        status = scrape(href)
        scraped_links[href] = status
        return status


def get_status(href):
    try:
        res = requests.get(href, headers=header, timeout=10)
    except requests.exceptions.Timeout:
        return "Timeout Error"
    else:
        return res.status_code


def scrape(href):
    """Checks the status of the link and returns the status code 200 or the error encountered.

    Args:
        link (bs4.element.Tag): The anchor tag extracted using BeautifulSoup which is to be checked

    Returns:
        String or Number: Error encountered or Status code 200
    """
    analyse = urlsplit(href)
    if analyse.scheme == "" or analyse.scheme in ["https", "http"]:
        if analyse.scheme == "":
            analyse = analyse._replace(scheme="https")
        href = analyse.geturl()
        res = get_status(href)
        return res
    elif analyse.scheme == "mailto":
        return "ignore"
    else:
        return "Invalid protocol detected"


def create_base_link(filename):
    """Generates base URL on which the license file will be displayed

    Args:
        filename (str): Name of the license file

    Returns:
        str: Base URL of the license file
    """
    base = "https://creativecommons.org"
    parts = filename.split("_")

    if parts[0] == "samplingplus":
        extra = "/licenses/sampling+"
    elif parts[0].startswith("zero"):
        extra = "/publicdomain/" + parts[0]
    else:
        extra = "/licenses/" + parts[0]

    extra = extra + "/" + parts[1]
    if parts[0] == "samplingplus" and len(parts) == 3:
        extra = extra + "/" + parts[2] + "/legalcode"
        return base + extra

    if len(parts) == 4:
        extra = extra + "/" + parts[2]
    extra = extra + "/legalcode"
    if len(parts) >= 3:
        extra = extra + "." + parts[-1]
    return base + extra


def verbose_print(*args, **kwargs):
    """Prints only if -v or --verbose flag is set
    """
    if verbose:
        print(*args, **kwargs)


def output_write(*args, **kwargs):
    """Prints to output file is --output-error flag is set
    """
    if output_err:
        kwargs["file"] = output
        print(*args, **kwargs)


all_links = get_all_license()

base = "https://raw.githubusercontent.com/creativecommons/creativecommons.org/master/docroot/legalcode/"

for licens in all_links:
    caught_errors = 0
    check_extension = licens.string.split(".")
    page_url = base + licens.string
    print("\n")
    print("Checking:", licens.string)
    if check_extension[-1] != "html":
        verbose_print("Encountered non-html file -\t skipping", licens.string)
        continue
    filename = licens.string[:-5]
    base_url = create_base_link(filename)
    print("URL:", base_url)
    source_html = requests.get(page_url, headers=header)
    license_soup = BeautifulSoup(source_html.content, "lxml")
    links_in_license = license_soup.find_all("a")
    verbose_print("No. of links found:", len(links_in_license))
    verbose_print("Errors and Warnings:")
    for link in links_in_license:
        try:
            href = link["href"]
        except KeyError:
            # if there exists an <a> tag without href
            verbose_print("Found anchor tag without href -\t", link)
            continue
        if href[0] == "#":
            verbose_print("Skipping internal link -\t", link)
            continue
        status = check_existing(link, base_url)
        if status not in [200, "ignore"]:
            caught_errors += 1
            if caught_errors == 1:
                if not verbose:
                    print("Errors:")
                output_write("\n{}\nURL: ".format(licens.string, base_url))
            err_code = 1
            print(status, "-\t", link)
            output_write(status, "-\t", link)

if output_err:
    print("\nError file present at: ", output.name)

sys.exit(err_code)
