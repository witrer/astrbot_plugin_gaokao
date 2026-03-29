import re

def _latex_to_html(text):
    def _convert_formula(m):
        f = m.group(1)
        greek = {
            'alpha': '\u03b1', 'beta': '\u03b2', 'gamma': '\u03b3', 'delta': '\u03b4',
            'epsilon': '\u03b5', 'theta': '\u03b8', 'lambda': '\u03bb', 'pi': '\u03c0',
            'sigma': '\u03c3', 'phi': '\u03c6', 'omega': '\u03c9',
            'Delta': '\u0394', 'Sigma': '\u03a3', 'Omega': '\u03a9',
        }
        for k, v in greek.items():
            f = f.replace('\\' + k, v)
        replacements = {
            '\\triangle': '\u25b3', '\\angle': '\u2220', '\\perp': '\u22a5',
            '\\times': '\u00d7', '\\cdot': '\u00b7', '\\pm': '\u00b1',
            '\\leq': '\u2264', '\\geq': '\u2265', '\\neq': '\u2260',
            '\\infty': '\u221e', '\\sqrt': '\u221a', '\\sum': '\u2211',
            '\\int': '\u222b', '\\in': '\u2208', '\\subset': '\u2282',
            '\\rightarrow': '\u2192', '\\Rightarrow': '\u21d2',
            '\\left': '', '\\right': '', '\\quad': '  ',
            '\\text': '', '\\mathrm': '', '\\mathbf': '',
        }
        for k, v in replacements.items():
            f = f.replace(k, v)
        for fn in ['sin', 'cos', 'tan', 'cot', 'sec', 'csc', 'arcsin', 'arccos', 'arctan', 'ln', 'lg', 'log', 'lim']:
            f = f.replace('\\' + fn, fn)
        f = re.sub(r'\\frac\s*\{([^}]*)\}\s*\{([^}]*)\}', r'(\1)/(\2)', f)
        f = re.sub(r'\\sqrt\{([^}]*)\}', lambda m: '\u221a(' + m.group(1) + ')', f)
        f = re.sub(r'\^\{([^}]*)\}', r'<sup>\1</sup>', f)
        f = re.sub(r'\^(\w)', r'<sup>\1</sup>', f)
        f = re.sub(r'_\{([^}]*)\}', r'<sub>\1</sub>', f)
        f = re.sub(r'_(\w)', r'<sub>\1</sub>', f)
        f = re.sub(r'\\[a-zA-Z]+', '', f)
        f = f.replace('{', '').replace('}', '')
        return f

    text = re.sub(r'\$\$(.+?)\$\$', _convert_formula, text, flags=re.DOTALL)
    text = re.sub(r'\$(.+?)\$', _convert_formula, text, flags=re.DOTALL)
    return text

# Test with the actual question from the log
sample = r'(5 分) 已知 $a, b, c$ 分别为 $\triangle A B C$ 的三个内角 $A, B, C$ 的对边, $a=2$ 且 $(2+b)(\sin A-\sin B)=(c-b) \sin C$, 则 $\triangle A B C$ 面积的最大值为'
result = _latex_to_html(sample)
print("INPUT:")
print(sample)
print("\nOUTPUT:")
print(result)
