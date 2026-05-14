#!.trans/bin/python
'''
Created on 11 mai 2025
## pip install argostranslate polib
@author: denis
'''
import argparse
import os
import polib
import argostranslate.package
import argostranslate.translate

DJANGO_PROJECT = "test_tube_scanner"

def install_translation_model(from_lang="en", to_lang="fr"):
    print("Cheching translation model...")
    argostranslate.package.update_package_index()
    available_packages = argostranslate.package.get_available_packages()

    try:
        package_to_install = next(
            p for p in available_packages if p.from_code == from_lang and p.to_code == to_lang
        )
        print(f"Loading model {from_lang} >> {to_lang}...")
        argostranslate.package.install_from_path(package_to_install.download())
        print("Installation model ")
    except StopIteration:
        print("No models found for this language pair.")
        exit(1)


def translate_po_file(input_path, output_path, from_lang="en", to_lang="fr"):
    print(f"Loading file {input_path}...")
    po = polib.pofile(input_path)

    print("Start traduction...")
    for entry in po:
        if entry.msgstr.strip() == "" and entry.msgid.strip():
            try:
                translation = argostranslate.translate.translate(entry.msgid, from_lang, to_lang)
                entry.msgstr = translation
            except Exception as e:
                print(f"Translation error: {entry.msgid}\n{e}")
                continue

    po.save(output_path)
    print(f"End of translation. Output file in: {output_path}")


def main(app, from_lang, to_lang):
    INPUT_FILE = f'{app}/locale/{from_lang}/LC_MESSAGES/django.po'
    OUTPUT_FILE = f'{app}/locale/{to_lang}/LC_MESSAGES/django.po'
    install_translation_model(from_lang, to_lang)
    translate_po_file(INPUT_FILE, OUTPUT_FILE, from_lang, to_lang)
    
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translation for Django")
    parser.add_argument("--app", type=str, default='home', help="Django application name")
    parser.add_argument("--from_lang", type=str, default="fr", help="From language")
    parser.add_argument("--to_lang", type=str, default='en', help="To language", required=True)
    args = parser.parse_args()
    
    main(f'{DJANGO_PROJECT}/{args.app}', args.from_lang, args.to_lang)
    exit(0)
