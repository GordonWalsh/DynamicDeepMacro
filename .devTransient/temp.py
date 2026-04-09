"""
Quick script to redo some test argument orders
"""
import re
items = [(["hello ", "<world>"], ["TokenType.LITERAL", "TokenType.INVOCATION"]), (["The ", "<color>", " ", "<animal>", " ran"], ["TokenType.LITERAL", "TokenType.INVOCATION", "TokenType.LITERAL", "TokenType.INVOCATION", "TokenType.LITERAL"]), (["<start>", " of text"], ["TokenType.INVOCATION", "TokenType.LITERAL"]), (["end of ", "<text>"], ["TokenType.LITERAL", "TokenType.INVOCATION"]), (["<first>", "<second>"], ["TokenType.INVOCATION", "TokenType.INVOCATION"]), (["text ", "<outer <inner> content>"], ["TokenType.LITERAL", "TokenType.INVOCATION"]), (["a ", "<outer {inner} content>"], ["TokenType.LITERAL", "TokenType.INVOCATION"]), (["text ", "<>", " more"], ["TokenType.LITERAL", "TokenType.INVOCATION", "TokenType.LITERAL"]), (["text ", r"<content\> still inside>"], ["TokenType.LITERAL", "TokenType.INVOCATION"]), (["a ", "<b>", " c ", "{d}", " e"], ["TokenType.LITERAL", "TokenType.INVOCATION", "TokenType.LITERAL", "TokenType.GROUP", "TokenType.LITERAL"]), (["<foo {bar>", " }"], ["TokenType.INVOCATION", "TokenType.LITERAL"]), (["<a ", "{b> }"], ["TokenType.LITERAL", "TokenType.GROUP"]), (["{<b> }"], ["TokenType.GROUP"])]
results=[]
replaces=[]
def clean(str):
    return re.sub(r'[\'"](TokenType\.\w*)[\'"]', r'\1', str)
for item in items:
    result = list(zip(item[0], item[1]))
    results.append(result)
    replaces.append((clean(repr(item).replace("'", '"')), clean(repr(result).replace("'", "'"))))
with open("./test_suite.py", "r") as file:
    content = file.read()
    for replace in replaces:
        print(f"{replace[0]}\t||\t{replace[1]}")
        print(content.find(replace[0]))
        content = content.replace(replace[0], replace[1])
        # print(re.search(r'^.*' + re.escape(replace[0]), content, re.MULTILINE))
        # content= re.sub(re.escape(replace[0]), replace[1], content)
with open('./temp_out.py', 'w') as outfile:
    outfile.write(content)