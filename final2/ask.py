import re
from nltk import pos_tag
### TREE OPS
import sys

inputFile = sys.argv[0]
with open(inputFile) as f:
    file = f.read()

def list_to_string(word_list):
    return ' '.join(word_list)

def tree_to_string(parsed_tree, lower=False):
    leaves = parsed_tree.leaves()
    if lower:
        leaves[0] = leaves[0].lower()
    return list_to_string(leaves)

#Returns traversal type
def first(parsed_tree):
    ancs = []
    while not isinstance(parsed_tree[0], str):
        ancs.append(parsed_tree)
        parsed_tree = parsed_tree[0]
    return (parsed_tree, ancs)

#gets the next thing that is not an anc of parsed_tree
def second_from_first(ancs):
    while len(ancs) > 0:
        anc = ancs.pop()
        if len(anc) > 1:
            return anc[1]
    return None

def val(parsed_tree):
    val = parsed_tree[0]
    if isinstance(val, str):
        return val
    return False

#Purges from the parsed tree the set of labels in purge_set
def purge(parsed_tree, purge_set):
    if isinstance(parsed_tree, str):
        return False
    if parsed_tree.label() in purge_set:
        return True
    length = len(parsed_tree)
    i = 0
    while i < length:
        res = purge(parsed_tree[i], purge_set)
        if res:
            del parsed_tree[i]
            length -= 1
        else:
            i += 1
    return False

#checks in a parsed_tree has a value in label-set
def has_label(parsed_tree, label_set):
    if isinstance(parsed_tree[0], str):
        return parsed_tree.label() in label_set
    contain = False
    for tree in parsed_tree:
        contain = contain or has_label(tree, label_set)
    return contain

#checks in a parsed_tree has a value in label-set
def has_string(parsed_tree, string_set):
    if isinstance(parsed_tree, str):
        return parsed_tree in string_set
    contain = False
    for tree in parsed_tree:
        contain = contain or has_string(tree, string_set)
    return contain


#Sentence Structure Tree
class SST():
    def __init__(self, label, children):
        self.label = label
        self.children = children

#Sentence Structure Leaf
class SSL():
    def __init__(self, label):
        self.label = label

simple_predicate = SST('ROOT', [SST('S', [SSL('NP'), SSL('VP'), SSL('.')])])

def satisfies_simple_pred(parse_tree):
    return satisfies_structure(parse_tree, simple_predicate)


def satisfies_structure(parsed_tree, structure):
    if isinstance(structure, SSL):
        return parsed_tree.label() == structure.label
    else:
        if parsed_tree.label() != structure.label or len(parsed_tree) != len(structure.children): return False
        for i in range(len(parsed_tree)):
            if satisfies_structure(parsed_tree[i], structure.children[i]) == False:
                return False
        return True

def count_pp(parsed_tree):
    if isinstance(parsed_tree, str):
        return 0
    else:
        sum = 1 if parsed_tree.label() == "PP" else 0
        for i in range(len(parsed_tree)):
            sum += count_pp(parsed_tree[i])
        return sum
            
def post_clean(sentence):
    sentence = sentence.replace('`` ', '\"')
    sentence = sentence.replace(' \'\'', '\"')
    sentence = sentence.replace('-RRB-', '')
    sentence = sentence.replace('-LRB-', '')
    sentence = sentence.replace(' -- ', '--')
    sentence = re.sub(';([.*? ^ \?]*) ?', '?', sentence)
    sentence = re.sub(' (?=[,:\.\?!\'%])', '', sentence)
    return sentence
        
def pre_clean(sentence):
    left_paren = 0
    remove = []
    sent_list = list(sentence)
    for i in range(len(sentence)):
        if left_paren > 0:
            remove.append(i)
        if sentence[i] == ')':
            left_paren -= 1
        if sentence[i] == '(':
            left_paren += 1
            if i > 0:
                remove.append(i-1)
            remove.append(i)
    for i in range(len(remove)-1, -1, -1):
        sent_list.pop(remove[i])
    return "".join(sent_list)



invertible_aux_verb = {'am', 'are', 'is', 'was', 'were', 'can', 'could',
                       'must', 'shall', 'should', 'will', 'would'}
invertible_special = {'does', 'did', 'has', 'had', 'have'}

purge_tree = {"PRN", "ADVP", "RB"} #WHNP with parent SBAR #JJ, JJR, ADJP, S with parent NP

proper_nouns = {"NNP", "NNPS"}
nouns = {"NNP", "NNPS"}
valid_determiners = {"the", "a"}
unclear_referral = {'this', 'that', 'these', 'those', 'it', 'their', 'they'}

class Questions():
    def __init__(self, sentences, parser, sp):
        self.sentences = sentences
        self.parser = parser #CoreNLPParser()
        self.sp = sp #spacy.load('en_core_web_sm')

    def is_invertible(self, s, next_phrase):
        if isinstance(s, str):
            return (s.lower() in invertible_aux_verb or 
                    s.lower() in invertible_special and next_phrase == "VP")
        return False

    def binary_question_from_tree(self, parsed_tree):
        sentence = parsed_tree[0]
        assert(sentence.label() == "S")
        np = sentence[0]
        vp = sentence[1]
        assert(np.label() == 'NP')
        assert(vp.label() == 'VP')
        if (has_label(np, {'VP'})):
            return None
        
        np_first, np_ancs = first(np)
        noun_label = np_first.label()

        if (not has_string(np, unclear_referral) and has_label(np_ancs[-1], nouns)):
            subject = tree_to_string(np, noun_label not in proper_nouns)
            remain = vp.leaves()[1:]
            vp_first, vp_ancs = first(vp)
            second = second_from_first(vp_ancs)
            if self.is_invertible(val(vp_first), second.label()):
                return list_to_string([val(vp_first).capitalize(), subject] + remain) + "?"
            else:
                #Add Do
                verb_label = vp_first.label()
                lemma = self.sp(val(vp_first))[0].lemma_
                if verb_label in ["VBP", "VBZ", "VBG"]:
                    return list_to_string(["Does", subject, lemma] + remain) + " ?"
                elif verb_label in ["VBD", "VBN"]: #past tense
                    return list_to_string(["Did", subject, lemma] + remain) + " ?"
        return None
    
    def wh_questions_from_tree(self, parsed_tree):
        question = []
        sentence = parsed_tree[0]
        assert(sentence.label() == 'S')
        np = sentence[0]
        vp = sentence[1]

        vpWord = " ".join(vp.leaves())
        npWord = " ".join(np.leaves())
        plural = False
        if (has_label(np, {'NNS', 'NNPS'})):
            plural = True
        doc = self.sp(npWord)
        prev = None
        for ent in doc.ents:
            text = ent.text
            label = ent.label_
            if prev != None and label != prev:
                return None
            prev = label
            if label == 'ORG':
                question.append(f"What {vpWord} ?")
            elif label == 'PERSON':
                question.append(f"Who {vpWord} ?")
            elif label == 'NORP':
                question.append(f"Which {'groups' if plural else 'group'} {vpWord} ?")
            elif label == 'TIME' or label == 'DATE':
                question.append(f"When {vpWord} ?")
            elif label == 'GPE':
                question.append(f"Which {'bodies' if plural else 'body'} {vpWord} ?")
            elif label == 'EVENT' or label == 'PRODUCT':
                question.append(f"What {vpWord} ?")
        return question

    def get_questions(self):
        parsed_list = []
        total = 0
        matched = 0
        failed = 0
        for i in range(len(self.sentences)): 
            sentence = self.sentences[i]
            try: 
                sentence = pre_clean(sentence)
                parse = next(self.parser.raw_parse(sentence))
                purge(parse, purge_tree)
                if satisfies_simple_pred(parse):
                    pp_count = count_pp(parse)
                    binary_question = self.binary_question_from_tree(parse)
                    wh_questions = self.wh_questions_from_tree(parse)
                    if binary_question != None:
                        matched += 1
                        parsed_list.append((post_clean(binary_question), i, pp_count))
                    for q in wh_questions:
                        parsed_list.append((post_clean(q), i, pp_count))
                    total += 1
            except Exception as e:
                failed += 1
        return parsed_list, (total, matched, failed)
            

PP_LIMIT = 2
COMMA_LIMIT = 2

def contains(question, phrase_list):
    for phrase in phrase_list:
        if phrase.text in question:
            return True
    return False

def rank(indexed_questions, rank_phrases):
    rank1 = [] #satisfies all constraints
    rank2 = [] #fails one constraint
    rank3 = [] #fails two constraints
    for (question, i, pp_count) in indexed_questions:
        fails = 0
        comma_count = question.count(",")
        if pp_count > PP_LIMIT:
            fails += 1
        if comma_count > COMMA_LIMIT:
            fails += 1
        if len(question) < 30 or len(question) > 150:
            fails += 1
        
        if fails == 0 and pp_count < PP_LIMIT and comma_count < COMMA_LIMIT:
            rank1.append(question)
        elif fails == 0 and (pp_count == PP_LIMIT or comma_count == COMMA_LIMIT):
            rank2.append(question)
        if fails > 0:
            rank3.append(question)
    finalrank = dict()
    for question in rank1:
        flag = False
        for p in rank_phrases:
            if contains(question, p.chunks):
                finalrank[question] = p.rank
                break
    finalrank2 = dict()
    for question in rank2:
        flag = False
        for p in rank_phrases:
            if contains(question, p.chunks):
                finalrank2[question] = p.rank
                break
    sort1 = sorted(finalrank, key=lambda key: -finalrank[key])
    sort2 = sorted(finalrank2, key=lambda key: -finalrank2[key])
    return sort1 + sort2 + rank3

import nltk
from nltk.parse.corenlp import CoreNLPServer
from nltk.parse.corenlp import CoreNLPParser
from nltk.parse.corenlp import CoreNLPDependencyParser
from nltk.tree import Tree
import os
import requests
import spacy
import neuralcoref
from pytextrank import TextRank

requests.post('http://[::]:9000/?properties={"annotators":"tokenize,ssplit,pos","outputFormat":"json"}', 
              data = {'data': "tmp"}).text

parser = CoreNLPParser()
tr = TextRank()
sp = spacy.load('en_core_web_lg')
neuralcoref.add_to_pipe(sp)
sp.add_pipe(tr.PipelineComponent, name="textrank", last=True)
'''
with open(f'./../Development_data/set2/a5.txt', 'r') as f:
    file = (f.read())
'''
def get_resolved(doc, clusters):
    ''' Return a list of utterrances text where the coref are resolved to the most representative mention'''
    sentences = [sent.string.strip() for sent in doc.sents]
    token_labels = []
    for i in range(len(sentences)):
        for j in range(len(list(tok.text_with_ws for tok in sp(sentences[i])))):
            token_labels.append(i)
    resolved = list(tok.text_with_ws for tok in doc)
    if len(resolved) != len(token_labels):
        return ''.join(resolved)
    for cluster in clusters:
        seen = set()
        for coref in cluster:
            if coref != cluster.main and token_labels[coref.start] not in seen:
                resolved[coref.start] = cluster.main.text + doc[coref.end-1].whitespace_
                for i in range(coref.start+1, coref.end):
                    resolved[i] = ""
            seen.add(token_labels[coref.start])
    return ''.join(resolved)

sentences = []

tmp_file = sp(file)
rank_phrases = tmp_file._.phrases
coref_text = get_resolved(tmp_file, tmp_file._.coref_clusters)
new_sentences = [sent.string.strip() for sent in sp(coref_text).sents]
sentences.extend(new_sentences)

i = 0
while i < len(sentences):
    
    if sentences[i][-1] != ".":
        sentences.pop(i)
        if len(sentences) > i:
            sentences.pop(i)
    elif ord(sentences[i][0]) > 90 or ord(sentences[i][0]) < 65:
        sentences.pop(i)
    else:
        i += 1

q = Questions(sentences, parser, sp)
indexed_questions, performance = q.get_questions()
questions = rank(indexed_questions, rank_phrases)

nquestion = sys.argv[1]
print(questions[:nquestion])