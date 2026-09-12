"""
Debug test for ouvrage template scenario
"""
import sys
sys.path.insert(0, 'src')

from wikipedia_maintenance.utils.bare_url_helper import BareUrlHelper, BareUrlRef
from wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplateHelper

helper = BareUrlHelper()
template_helper = ReferenceTemplateHelper()

ref = BareUrlRef(
    dead_url="https://example.com/book",
    dead_url_start=0,
    dead_url_end=22,
    replacement_end=22,
    line_start=0,
    line_end=100,
    existing_archive_url=None,
    context_text="https://example.com/book",
    link_label=None,
    replacement_start=0
)

print("Testing ouvrage template generation...")
result = helper.build_repaired_reference_template(
    ref=ref,
    archive_url="https://web.archive.org/web/20200101/https://example.com/book",
    archive_date="20200101",
    title_hint="Book Title",
    provider="WaybackMachine",
    template_name='ouvrage',
    extra_params=None,
    template_helper=template_helper
)

print(f"Result: {result}")
print(f"Result is None: {result is None}")

if result is None:
    print("Template generation returned None - checking if this is expected behavior")
    print("This might be because ouvrage templates don't support archive parameters")
