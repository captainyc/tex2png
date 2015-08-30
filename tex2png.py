import re
import os
import sys
import urllib
import glob
import argparse
from itertools import repeat
import tarfile
import multiprocessing
import shutil


def find_token(string):
	string = re.search(r"^\s*(.*)",string).group(1)
	token = ''
	rest = ''
	if string == '':
		pass
	elif re.search(r"^{",string):
		left = 1 
		right = 0
		for i in range(1,len(string)):
			if string[i] == '{':
				left += 1
			elif string[i] == '}':
				right += 1
			if left == right:
				token = string[0:i+1]
				rest = string[i+1:]
				break
	else:
		match = re.search(r"^(\\\W|\\[A-Za-z]+)(.*)",string)
		if match:
			token = match.group(1)
			rest = match.group(2)
		else:
			token = string[0]
			if len(string)>1:
				rest = string[1:]
	return [token,rest]

newcPat = re.compile( r"^\s*\\newcommand\*?\s*{?\s*\\(\W|[A-Za-z0-9@]+)\s*}?\s*([^%\n]*)")
renewcPat = re.compile( r"^\s*\\renewcommand\*?\s*{?\s*\\(\W|[A-Za-z0-9@]+)\s*}?\s*([^%\n]*)")
defPat = re.compile( r"^\s*\\def\s*{?\s*\\(\W|[A-Za-z0-9@]+)\s*}?\s*([^%\n]*)")
mathPat = re.compile( r"\\DeclareMathOperator\*?{?\\([A-Za-z]+)}?{((:?[^{}]*{[^}]*})*[^}]*)}" )

class macro:
	def __init__(self, line):
		self.defined = False
		self.multiline = False
		# check if macros are defined within macros
		
		# newcommand & renewcommand
		match = ''
		if newcPat.search(line):
			match = newcPat.search(line)
		elif renewcPat.search(line):
			match = renewcPat.search(line)

		if match:
			leftbracket = len(re.findall('{', match.group(2))) - len(re.findall(r'\\{', match.group(2)))
			rightbracket = len(re.findall('}', match.group(2))) - len(re.findall(r'\\}', match.group(2)))
			if leftbracket == rightbracket:
				if len(re.findall(r"\\newcommand(?=\W)|\\renewcommand(?=\W)|\\def(?=\W)|\\DeclareMathOperator(?=\W)", line)) > 1:
					pass
				elif re.search(r"(\\newcommand|\\renewcommand|\\def)[^%]*\\fi\W", line):
					pass
				elif re.search(r"@",line):
					pass
				elif match.group(1):
					self.name = match.group(1)
					content = match.group(2)
					if len(re.findall('{', content)) == 0:
						content = '{'+content+'}'
					match2 = re.search(r"^\s*(\[(\d)\])?\s*(\[(.*)\])?\s*{(.*)}", content)
					if match2:
						self.defined = True
						if re.search(r"^{.*}$|\\begin|\\end|\\left|\\right",match2.group(5)):
							self.definition = match2.group(5)
						else:
							self.definition = '{'+match2.group(5)+'}'
						if match2.group(1):
							self.narg = int(match2.group(2))
							for i in range(0,self.narg):
								if not re.search(r"#"+str(i+1),self.definition):
									self.defined = False
									break
							if match2.group(3):
								self.default = match2.group(4)
							else:
								self.default = ''
						else:
							self.narg = 0
							self.default = ''
					else:
						self.multiline = True
			elif leftbracket > rightbracket:
				self.multiline = True
		# def
		elif defPat.search(line):
			match = defPat.search(line)
			leftbracket = len(re.findall('{', match.group(2))) - len(re.findall(r'\\{', match.group(2)))
			rightbracket = len(re.findall('}', match.group(2))) - len(re.findall(r'\\}', match.group(2)))
			if leftbracket == rightbracket:
				if len(re.findall(r"\\newcommand(?=\W)|\\renewcommand(?=\W)|\\def(?=\W)|\\DeclareMathOperator(?=\W)", line)) > 1:
					pass
				elif re.search(r"(\\newcommand|\\renewcommand|\\def)[^%]*\\fi\W", line):
					pass
				elif re.search(r"@",line):
					pass
				elif match.group(1):
					self.name = match.group(1)
					content = match.group(2)
					if len(re.findall('{', content)) == 0:
						content = '{'+content+'}'
					match2 = re.search(r"^([^{]*){(.*)}", content)
					if match2:
						self.defined = True
						if re.search(r"^{.*}$|\\begin|\\end|\\left|\\right",match2.group(2)):
							self.definition = match2.group(2)
						else:
							self.definition = '{'+match2.group(2)+'}'
						if match2.group(1):
							self.narg = len(re.findall(r"#",match2.group(1)))
							self.default = ''
							for i in range(0,self.narg):
								if not re.search(r"#"+str(i+1),self.definition):
									self.defined = False
									break
						else:
							self.narg = 0
							self.default = ''
					else:
						self.multiline = True
			elif leftbracket > rightbracket:
				self.multiline = True
		# DeclareMathOperator
		elif mathPat.search(line):
			match = mathPat.search(line)
			self.name = match.group(1)
			self.definition = '{\\operatorname{' + match.group(2) + '}}'
			self.narg = 0
			self.default = ''
			self.defined = True

	def check_already_defined(self, line):
		if re.match(r"\W", self.name):
			if self.name == '.':
				check = re.compile(r"(\\def|\\newcommand|\\renewcommand|\\DeclareMathOperator)[{\s]*\\\.\W")
			elif self.name == '*':
				check = re.compile(r"(\\def|\\newcommand|\\renewcommand|\\DeclareMathOperator)[{\s]*\\\*\W")
			elif self.name == '?':
				check = re.compile(r"(\\def|\\newcommand|\\renewcommand|\\DeclareMathOperator)[{\s]*\\\?\W")
			elif self.name == '+':
				check = re.compile(r"(\\def|\\newcommand|\\renewcommand|\\DeclareMathOperator)[{\s]*\\\+\W")
			elif self.name == '-':
				check = re.compile(r"(\\def|\\newcommand|\\renewcommand|\\DeclareMathOperator)[{\s]*\\\-\W")
			elif self.name == '[':
				check = re.compile(r"(\\def|\\newcommand|\\renewcommand|\\DeclareMathOperator)[{\s]*\\\[\W")
			elif self.name == ']':
				check = re.compile(r"(\\def|\\newcommand|\\renewcommand|\\DeclareMathOperator)[{\s]*\\\]\W")
			elif self.name == '(':
				check = re.compile(r"(\\def|\\newcommand|\\renewcommand|\\DeclareMathOperator)[{\s]*\\\(\W")
			elif self.name == ')':
				check = re.compile(r"(\\def|\\newcommand|\\renewcommand|\\DeclareMathOperator)[{\s]*\\\)\W")
			elif self.name == '^':
				check = re.compile(r"(\\def|\\newcommand|\\renewcommand|\\DeclareMathOperator)[{\s]*\\\^\W")
			elif self.name == ':':
				check = re.compile(r"(\\def|\\newcommand|\\renewcommand|\\DeclareMathOperator)[{\s]*\\\:\W")
			elif self.name == '=':
				check = re.compile(r"(\\def|\\newcommand|\\renewcommand|\\DeclareMathOperator)[{\s]*\\\=\W")
			else:
				check = re.compile(r"(\\def|\\newcommand|\\renewcommand|\\DeclareMathOperator)[{\s]*\\" + self.name + "\W")
		else:
			check = re.compile(r"(\\def|\\newcommand|\\renewcommand|\\DeclareMathOperator)[{\s]*\\" + self.name + "\W")
		if check.search(line):
			return True
		else:
			return False

	def match(self, line):
		if re.match(r"\W", self.name):
			if self.name == '.':
				mat = re.compile(r"^(.*)\\\.(.*)")
			elif self.name == '*':
				mat = re.compile(r"^(.*)\\\*(.*)")
			elif self.name == '?':
				mat = re.compile(r"^(.*)\\\?(.*)")
			elif self.name == '+':
				mat = re.compile(r"^(.*)\\\+(.*)")
			elif self.name == '-':
				mat = re.compile(r"^(.*)\\\-(.*)")
			elif self.name == '[':
				mat = re.compile(r"^(.*)\\\[(.*)")
			elif self.name == ']':
				mat = re.compile(r"^(.*)\\\](.*)")
			elif self.name == '(':
				mat = re.compile(r"^(.*)\\\((.*)")
			elif self.name == ')':
				mat = re.compile(r"^(.*)\\\)(.*)")
			elif self.name == '^':
				mat = re.compile(r"^(.*)\\\^(.*)")
			elif self.name == ':':
				mat = re.compile(r"^(.*)\\\:(.*)")
			elif self.name == '=':
				mat = re.compile(r"^(.*)\\\=(.*)")
			elif self.name == '\\':
				mat = re.compile(r"^(.*)\\\\(.*)")
			else:
				mat = re.compile(r"^(.*)\\" + self.name + "(.*)")
		else:
			mat = re.compile(r"^(.*)\\" + self.name + "(?![A-Za-z0-9])(.*)")
		return mat.search(line)

	def temp_def(self, args):
		temp = self.definition
		for i in range(0,self.narg):
			temp = temp.replace(r"#"+str(i+1),args[i])
		return temp

	def parse(self, line):
		if self.check_already_defined(line):
			return [line, False]
		current = re.search(r"[^\n]*", line).group()
		match = self.match(current)
		while match:
			if self.narg == 0:
				current = match.group(1) + self.definition + match.group(2)
			else:
				args = []
				if not self.default:
					rest = match.group(2)
					for i in range(0,self.narg):
						token = find_token(rest)
						if not token[0]:
							return [line, True]
						args.append(token[0])
						rest = token[1]
				else:
					rest = match.group(2)
					argmatch = re.search(r"^\s*\[([^\]])\](.*)",rest)
					if argmatch:
						args.append(argmatch.group(1))
						rest = argmatch.group(2)
					else:
						args.append(self.default)
					for i in range(0,self.narg-1):
						token = find_token(rest)
						if not token[0]:
							return [line, True]
						args.append(token[0])
						rest = token[1]
				current = match.group(1) + self.temp_def(args) + rest
			match = self.match(current)
		return [current+'\n', False]

def cut_extension(filename, ext):
	file = filename
	index = filename.rfind(ext)
	if 0 <= index and len(file)-len(ext) == index:
		file = file[:index]
	return file

def decomment(line):
	match = re.search(r"([^\n%]*)(.*)", line)
	newline = match.group(1)
	line = match.group(2)
	while re.search(r"\\$", newline):
		if len(line)==0:
			break
		match = re.search(r"([^\n%]*)(.*)", line[1:])
		newline += '%'+match.group(1)
		line = match.group(2)
	return newline+'\n'

def match_start(start):
	if re.search(r'begin', start):
		return re.sub(r'begin', 'end', start)
	elif start == '\\[':
		return '\\]'
	elif start == '$$':
		return '$$'
	else:
		return ''

def delabel(term):
	if term.find("*")<0:
		term = term.replace("equation","equation*")
		term = term.replace("align","align*")
		term = term.replace("eqnarray","eqnarray*")
	return term

def remove_path(filename):
	match = re.search(r"(.*)/(.*)",filename)
	if match:
		return match.group(2)
	else:
		return filename

def tex2png(input, output='out'):
	inputHandler = open(input, 'r')
	unread = inputHandler.readlines()
	inputHandler.close()
	multilineFlag = False
	macroDict = {}
	preamble = []
	formulas = []

	formulaPat = re.compile(r"(\\begin{equation}|\\begin{equation*}|\\begin{align}|\\begin{align*}|\\\[|\\begin{eqnarray}|\\begin{eqnarray*})(.*)")

	while True:
		if multilineFlag:
			current += re.search(r".*",decomment(current)).group() + ' ' + unread[0]
		else:
			current = unread[0]
		unread = unread[1:]
		if re.search(r"\\input", current):
			matchInput = re.search(r"(.*)\\input{[./]*(.*?)}(.*)", current)
			if matchInput:
				inputPath = os.getcwd() + '/' + cut_extension(matchInput.group(2),'.tex') + '.tex'
				if os.path.exists(inputPath):
					inputFile = open(inputPath, 'r')
					unread = inputFile.readlines() + [matchInput.group(3)+'\n'] + unread
					current = matchInput.group(1)+'\n'
				else:
					current = matchInput.group(1) + ' ' + matchInput.group(3)+'\n'
			else:
				matchInput = re.search(r"(.*)\\input\s+([^\s]+)(.*)", current)
				if matchInput:
					inputPath = os.getcwd() + '/' + cut_extension(matchInput.group(2),'.tex') + '.tex'
					if os.path.exists(inputPath):
						inputFile = open(inputPath, 'r')
						unread = inputFile.readlines() + [matchInput.group(3)+'\n'] + unread
						current = matchInput.group(1)+'\n'
					else:
						current = matchInput.group(1) + ' ' + matchInput.group(3)+'\n'
		if re.search(r"\\begin{document}", current):
			break
		elif re.search(r"\\documentclass", decomment(current)):
			preamble.append("\\documentclass{standalone}\n")
			preamble.append("\\usepackage{amsmath}\n")
			preamble.append("\\usepackage{amsfonts}\n")
			preamble.append("\\usepackage{amssymb}\n")
			preamble.append("\\usepackage{amsthm}\n")
			preamble.append("\\usepackage{bm}\n")
			preamble.append("\\usepackage{varwidth}\n")
		elif re.search(r"(\\newcommand|\\def)(.*)\\(begin|end){(equation|align)", current):
			newmacro = macro(current)
			multilineFlag = newmacro.multiline
			if multilineFlag:
				continue
			elif newmacro.defined:
				macroDict[newmacro.name] = newmacro
		elif re.search(r"\\(usepackage|RequirePackage)",current):
			preamble.append('% '+current)
			#preamble.append(current)
		else:
			preamble.append(current)

	temp = []
	multilineFlag = False
	while len(unread)>0:
		if multilineFlag:
			current += re.search(r".*",current).group() + ' ' + decomment(unread[0])
		else:
			current = decomment(unread[0])
		unread = unread[1:]
		if re.search(r"\\input", current):
			matchInput = re.search(r"(.*)\\input{[./]*(.*?)}(.*)", current)
			if matchInput:
				inputPath = os.getcwd() + '/' + cut_extension(matchInput.group(2),'.tex') + '.tex'
				if os.path.exists(inputPath):
					inputFile = open(inputPath, 'r')
					unread = inputFile.readlines() + [matchInput.group(3)+'\n'] + unread
					current = matchInput.group(1)+'\n'
				else:
					current = matchInput.group(1) + ' ' + matchInput.group(3)+'\n'
			else:
				matchInput = re.search(r"(.*)\\input\s+([^\s]+)(.*)", current)
				if matchInput:
					inputPath = os.getcwd() + '/' + cut_extension(matchInput.group(2),'.tex') + '.tex'
					if os.path.exists(inputPath):
						inputFile = open(inputPath, 'r')
						unread = inputFile.readlines() + [matchInput.group(3)+'\n'] + unread
						current = matchInput.group(1)+'\n'
					else:
						current = matchInput.group(1) + ' ' + matchInput.group(3)+'\n'
		if re.search(r"(\\newcommand|\\def)(.*)\\(begin|end){(equation|align|eqnarray)", current):
			newmacro = macro(current)
			multilineFlag = newmacro.multiline
			if multilineFlag:
				continue
			elif newmacro.defined:
				macroDict[newmacro.name] = newmacro
				continue
		for x in macroDict:
			currentParsed = macroDict[x].parse(current)
			multilineFlag = currentParsed[1]
			if multilineFlag:
				break
			current = currentParsed[0]
		if multilineFlag:
			continue
		temp.append(current)
	unread = temp

	while len(unread)>0:
		current = unread[0]
		unread = unread[1:]
		matchFormula = formulaPat.search(current)
		if matchFormula:
			start = matchFormula.group(1)
			if (start == '\\[') & (current.find('\\[')>0) & (current[current.find('\\[')-1]=='\\'):
				continue
			end = match_start(start)
			formula_temp = []
			formula_temp.append(delabel(start)+'\n')
			if re.search(r'\S',matchFormula.group(2)):
				current = matchFormula.group(2)+'\n'
			else:
				current = unread[0]
				unread = unread[1:]
			while current.find(end)<0:
				if re.search(r'\S', current):
					formula_temp.append(current)
				current = unread[0]
				unread = unread[1:]
			ind = current.find(end)
			formula_temp.append(current[0:ind]+delabel(end)+'\n')
			if len(current)>ind+len(end)+1:
				unread = [ current[ind+len(end)] ] + unread
			formulas.append(formula_temp)

	i = 1
	for formula in formulas:
		currentoutput = output+'_%d'%i
		outputHandler = open(currentoutput+'.tex', 'w')
		for line in preamble:
			outputHandler.write(line)
		outputHandler.write("\n")
		outputHandler.write("\\begin{document}\n")
		outputHandler.write("\\begin{varwidth}{\linewidth}\n")
		for line in formula:
			outputHandler.write(line)
		outputHandler.write("\\end{varwidth}\n")
		outputHandler.write("\\end{document}\n")
		outputHandler.close()

		os.system('pdflatex -interaction=nonstopmode %s.tex' %currentoutput)
		#os.remove('%s.tex' % currentoutput)
		os.remove('%s.log' % currentoutput)
		if os.path.isfile('%s.pdf' % currentoutput):
			os.system('convert -density 300 %s.pdf -quality 90 %s.png' % (currentoutput, currentoutput))
			os.remove('%s.pdf' % currentoutput)
		if os.path.isfile('%s.aux' % currentoutput):
			os.remove('%s.aux' % currentoutput)
		if os.path.isfile('%s.out' % currentoutput):
			os.remove('%s.out' % currentoutput)
		i += 1

def gunzip_and_tex2png(tarball):
	tar = tarfile.open(tarball)
	tar.extractall()

	inputFile = None
	for file in filter(lambda x: '.tex' in x, tar.getnames()):
		fh = open(file, 'r')
		for line in fh:
			if re.search(r"^[^%]*\\begin{document}", line):
				inputFile = file
				break
		fh.close()

	tar.close()

	if inputFile:
		outputFile = tarball.replace('.tar.gz','')
		tex2png(inputFile, outputFile)
	else:
		print 'no main file found'

	shutil.rmtree(tarball.replace('.tar.gz',''))

	return

		

			
def main():
	parser = argparse.ArgumentParser(description = 'extract and convert equations from tex to png')

	parser.add_argument('inputName', help = 'input file or directory')
	parser.add_argument('-d', '--directory', action='store_true', help='indicates that inputFile is a directory of tarballs')

	args = parser.parse_args()

	if args.directory:
		tarballs = glob.glob(args.inputName + '/*.tar.gz')
		pool = multiprocessing.Pool(processes=1)
		pool.map(gunzip_and_tex2png, tarballs)
	else:
		tex2png(args.inputName)

	return


if __name__ == "__main__":
	main()