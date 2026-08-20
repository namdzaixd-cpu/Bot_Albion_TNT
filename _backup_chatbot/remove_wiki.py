import re
with open('bot/cogs/chat_ai.py', 'r', encoding='utf-8') as f: content = f.read()
start_idx = content.find('async def _search_wiki_async')
end_idx = content.find('@ailibrary_group.command(name="autowiki"')
if start_idx != -1 and end_idx != -1:
    content = content[:start_idx-4] + content[end_idx-4:]
    with open('bot/cogs/chat_ai.py', 'w', encoding='utf-8') as f: f.write(content)
    print('Removed wiki from chat_ai.py')
else:
    print('Could not find bounds')
