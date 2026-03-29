import zipfile, json

old_zip = zipfile.ZipFile('astrbot_plugin_gaokao_fixed.zip', 'r')
new_zip = zipfile.ZipFile('astrbot_plugin_gaokao_v2.zip', 'w', zipfile.ZIP_DEFLATED)

for item in old_zip.namelist():
    if item == 'astrbot_plugin_gaokao/_conf_schema.json':
        new_zip.write('_conf_schema.json', item)
    elif item == 'astrbot_plugin_gaokao/main.py':
        new_zip.write('main.py', item)
    elif item == 'astrbot_plugin_gaokao/metadata.yaml':
        new_zip.write('metadata.yaml', item)
    else:
        data = old_zip.read(item)
        new_zip.writestr(item, data)

old_zip.close()
new_zip.close()

z = zipfile.ZipFile('astrbot_plugin_gaokao_v2.zip', 'r')
print('Files in new zip:')
for n in z.namelist():
    print(f'  {n}')

conf = json.loads(z.read('astrbot_plugin_gaokao/_conf_schema.json'))
print(f"\nllm_provider special: {conf.get('llm_provider', {}).get('_special', 'N/A')}")
print(f"render_as_image type: {conf['render_as_image']['type']}")

main_py = z.read('astrbot_plugin_gaokao/main.py').decode('utf-8')
print(f"\nsession_waiter count: {main_py.count('session_waiter')}")
print(f"select_provider in config: {'yes' if 'select_provider' in conf.get('llm_provider', {}).get('_special', '') else 'no'}")
print(f"_try_send_tg_buttons count: {main_py.count('_try_send_tg_buttons')}")
print(f"max-width:420px count: {main_py.count('max-width:420px')}")
print(f"max-width:380px count: {main_py.count('max-width:380px')}")
z.close()
print('\nDone! v2.0 zip built successfully.')
