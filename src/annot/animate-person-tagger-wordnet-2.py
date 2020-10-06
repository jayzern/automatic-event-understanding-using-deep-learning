#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys
from nltk.corpus import wordnet as wn
from nltk.wsd import lesk

 
person_synsets = set([
        wn.synset('homo.n.02'),
        wn.synset('human.a.01'),
        wn.synset('human.a.02'),
        wn.synset('human.a.03'),
        wn.synset('person.n.01'),
        wn.synset('soul.n.01'),
   ])
people_synsets = set([
        wn.synset('living.n.02'),
        wn.synset('multitude.n.03'),
        wn.synset('people.n.01'),
        wn.synset('people.n.03'),
        wn.synset('social_group.n.01'),
    ])

#    org = [
#        wn.synset('organization.n.06'),
#        organization.n.04
#        organization.n.01
#        body.n.02 # under social_group
#    ]
    
animate_synsets = set([
        wn.synset('animate_being.n.01'),
        wn.synset('organism.n.01'),
        wn.synset('animal.n.01'),
        wn.synset('living_thing.n.01'),
    ])
animals_synsets = set([
        wn.synset('animal_group.n.01'),
    ])

synsets_with_sentient_arg = set([
        wn.synset('live.v.07'),
        wn.synset('live.v.02'),
        wn.synset('people.v.02'),
        wn.synset('people.v.01'),
        wn.synset('know.v.05'),
        wn.synset('exist.v.02'),
        wn.synset('populate.v.01'),
    ])
    
synsets_with_anim_arg = set([
 #       wn.synset(''),
        wn.synset('animal.s.01'),
        wn.synset('survive.v.01'),
        wn.synset('be.v.11'),
        wn.synset('live.v.03'),
        #wn.synset('live.v.05'),
    ])

def is_sentient(synsets):
    for synset in synsets:
        for person in person_synsets:
            if (person in synset._shortest_hypernym_paths(person)):
                return 1, synset.name(), person.name()
    for synset in synsets:
        for people in people_synsets:
            if (people in synset._shortest_hypernym_paths(people)):
                return 2, synset.name(), people.name()
    return 0, None, None

def is_animate(synsets):
    for synset in synsets:
        for anim in animate_synsets:
            if (anim in synset._shortest_hypernym_paths(anim)):
                return 1, synset.name(), anim.name()
    for synset in synsets:
        for anims in animals_synsets:
            if (anims in synset._shortest_hypernym_paths(anims)):
                return 2, synset.name(), anims.name()
    return 0, None, None

def is_sentient_pronoun(token):
    tokl = token.lower()
    if tokl in ("i","me","myself", "we","us","ourselves", "you","yourself", "he","him", "himself", "she", "her", "herself", "zee", "zem","zemself"):
        return u"SentiPron"
    if tokl in ("they", "them", "themselves", "themself"):
        return u"SentiPron?"
    if tokl in ("it", "itself"):
        return u"InanimPron" # perhaps better named "AnimPron?" because can refer to animals or inaminate
    return None

def tagtoken(token, tokens=None):
    senti_pron = is_sentient_pronoun(token)
    if senti_pron is not None:
        return senti_pron, None, None
    synsets = wn.synsets(token)
    if (synsets is None) or len(synsets) == 0:
        return u"None", None, None
    if tokens is None:
        tokens = [token]
    tokSynset = lesk(tokens, token)
    if (tokSynset is None) :
        return u"None", None, None
    
    is_senti, token_senti_synset, senti_synset = is_sentient([tokSynset])
    if is_senti > 0:
        return (u"Sentient" if (is_senti==1) else u"Sentients"), token_senti_synset, senti_synset    
    is_anim,  token_anim_synset,  anim_synset = is_animate([tokSynset])
    if is_anim > 0:
        return (u"Animate" if (is_anim==1) else u"Animates"), token_anim_synset,  anim_synset
    
    is_senti, token_senti_synset, senti_synset = is_sentient(synsets)
    if is_senti > 0:
        return (u"Sentient?" if (is_senti==1) else u"Sentients?"), token_senti_synset, senti_synset
    is_anim,  token_anim_synset,  anim_synset = is_animate(synsets)
    if is_anim > 0:
        return (u"Animate?" if (is_anim==1) else u"Animates?"), token_anim_synset,  anim_synset
    
    return u"None", None, None


def taggit(token, tokens) :
    tokSynset = lesk(tokens, token);
    animSenti = \
        "None" if (tokSynset is None) else \
        "Sentient" if (person in tokSynset._shortest_hypernym_paths(person)) else   \
        "Org"      if (animate in tokSynset._shortest_hypernym_paths(animate)) else \
        "Animate"  if (animate in tokSynset._shortest_hypernym_paths(animate)) else \
        "None"
    return "%s %s" % (str(tokSynset).replace("Synset('","").replace("')",""), animSenti)
 
def argType(word, synsets=None):
        SB = "somebody"
        ST = "something"
        nsSB = " " + SB
        nsST = " " + ST
        num_starts_with_somebody = 0
        num_starts_with_something = 0
        num_has_nonstart_somebody = 0
        num_has_nonstart_something = 0
        num_not_starting_with_somebody_or_something = 0
        num_not_having_nonstart_somebody_or_something = 0
        num_empty_patterns = 0
        
        if synsets is None:
            synsets = wn.synsets(word)
#        lemma = wn.morphy(word)
        for synset in synsets:
            for wlemma in synset.lemmas():
#                if wlemma.name() == lemma:
#                    print "lemma %s equals wlemma %s" % (lemma, wlemma.name())
                    for fs in wlemma.frame_strings():
#                        print("\t word: %s,\t lemma: %s,\t patterns: %s" % (word, wlemma.name(), wlemma.frame_strings()))
#                        if "" == fs:
#                            num_empty_patterns += 1
#                        else:
                            fsl = fs.lower()
                            has_nonstart_somebody = False
                            has_nonstart_something = False
                            starts_with_somebody = False
                            starts_with_something = False
                            if (len(fsl) >= 8) and (SB == fsl[:8]):
                                starts_with_somebody = True
                                num_starts_with_somebody += 1
                            if nsSB in fsl:
                                has_nonstart_somebody = True
                                num_has_nonstart_somebody += 1
                            if (len(fsl) >= 9) and (ST == fsl[:9]):
                                starts_with_something = True
                                num_starts_with_something += 1
                            if nsST in fsl:
                                has_nonstart_something = True
                                num_has_nonstart_something += 1
                            if not starts_with_somebody and not starts_with_something:
                                num_not_starting_with_somebody_or_something += 1
                            if not has_nonstart_somebody and not has_nonstart_something:
                                num_not_having_nonstart_somebody_or_something += 1

##                else:
##                    print "lemma %s not equals wlemma %s" % (lemma, wlemma.name())
#        print("DBG: ",
#              word, num_starts_with_somebody, num_starts_with_something, num_not_starting_with_somebody_or_something,
#              num_has_nonstart_somebody,num_has_nonstart_something,num_not_having_nonstart_somebody_or_something,
#              num_empty_patterns)
        return (num_starts_with_somebody, num_starts_with_something, num_not_starting_with_somebody_or_something,
                num_has_nonstart_somebody,num_has_nonstart_something,num_not_having_nonstart_somebody_or_something)
#                num_empty_patterns)

    
def test():
    for concept in (person_synsets, animate_synsets, synsets_with_sentient_arg, synsets_with_anim_arg ):
        print 
        for s in sorted(concept):
            print s, s.definition()
            for lemma in s.lemmas():
                print '\t', lemma, lemma.frame_strings()
        print
    taglines("""
I love Lucy
We want her
it is raining
    """.split('\n'))
    # TODO: add assert lines (for regression tests)

    
def taglines(lines, xml=False):
    print_extended_header = True
    for line in lines:
        if xml:
            print line,
            if '<tokenized>' in line:
                line = line.replace('<tokenized>','').replace('</tokenized>','')
            else:
                continue
        sent = unicode(line.strip())
        tokens = sent.split()
#        print "\n".join("%s %s" % (token, taggit(token,tokens)) for token in tokens)
#        print "\n".join("%s\t%s\t%s" % (token, tagtoken(token), argType(token)) for token in tokens)
#        print "\n".join("%s\t%s\t%s" % (token, tagtoken(token)[0], '\t'.join(str(a) for a in argType(token))) for token in tokens)
        if xml:
#            print '\t<tokenized>%s</tokenized>' % line.strip() #sent
            if print_extended_header:
                print '\t<senti-anim-wn columns="token, sentient-animate, num_starts_with_somebody, num_starts_with_something, num_not_starting_with_somebody_or_something, num_has_nonstart_somebody,num_has_nonstart_something,num_not_having_nonstart_somebody_or_something">'
                print_extended_header = False
            else:
                print '\t<senti-anim-wn>' 
        print "\n".join("%s%s\t%s\t%s" % (("\t\t" if xml else ""),
                                          token, tagtoken(token, tokens)[0],
                                          '\t'.join(str(a) for a in argType(token))) for token in tokens)
        if xml:
            print '\t</senti-anim-wn>'
        else:
            print
        
if __name__ == '__main__':
    xml = False
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            test()
            exit(0)
        elif sys.argv[1] == "xml":
            xml = True
        else:
            print "Unkown parameter: %s" % sys.argv[1]
            exit(1)
    taglines(sys.stdin, xml)

