
current_url="https://photoprism.augmentedbytech.com/library/albums"
print(f"Current url:{current_url}")
print(f"{'/library/albums' in current_url}")
print(f"{not current_url.endswith('/view')}")
print(f"{'/library/albums/' in current_url and not current_url.endswith('/view')}")