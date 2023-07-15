from bs4 import BeautifulSoup as bs
import requests
import pandas as pd
import numpy as np
from threading import Thread
from time import sleep, time
from urllib.request import urlopen, Request

tmdb = "https://www.themoviedb.org"
h = {'User-Agent': "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"}

class Item:
    
    def __init__(self, url=None, tipo='filme', id=None, name=None, html=None, download=True, thr=None):
        self.tipo = tipo
        if url != None and download:
            aux = url.replace(tmdb, '')
            self.id = int(aux.split('/')[-1]) if tipo == 'filme' else int(aux.split('/')[2].split('-')[0])
            self.thr = thr
            code = 0
            while code != 200:
                r = requests.get(url, headers=h, timeout=5)
                code = r.status_code
                if code == 404:
                    # print(f"status: {code} | {url} | T{thr}")
                    url = tmdb + '/tv/' + str(self.id)
                    # print('Novo url: ', url, f'| T{thr}')
                elif code == 429:
                    # print(f"status: {code} | {url} | T{thr}")
                    sleep(5)
            self.url = url
            self.html = bs(r.text, 'html.parser')
            self.name = self.html.find('div', {'class': 'title'}).find('a').text if tipo == 'filme' else self.html.find('h2', {'class': 'title'}).text
        else:
            self.id = id
            self.name = name
            self.html = html
            self.url = url
    
    def pegaId(self):
        return self.link.split('/')[-2] if self.tipo == 'filme' else self.link.split('/')[2].split('-')[0]
    
    def __str__(self):
        return f'{self.id} - {self.name} - {self.url} - {self.tipo} - html = {"TEM" if self.html != None else "Nao tem"}'


class Filme(Item):

    def __init__(self, url, thr=None):
        super().__init__(url=url, tipo='filme', thr=thr)
        aux = [(ator.find('a')['href'].split('/')[-1].split('-')[0], ator.find('p').text) 
               for ator in self.html.find_all('ol', {'class': 'people scroller'})[0].find_all('li')][:-1]
        self.elenco = [
            Item(
                id=int(x[0]),
                name=x[1], 
                tipo='ator', 
                url=f'{tmdb}/person/{x[0]}', 
                download=False)
            for x in aux]


class Ator(Item):
    def __init__(self, url,  thr=None):
        super().__init__(url=url, tipo='ator',  thr=thr)
        ids = [ (
                    int(filme.find('a')['href'].split('/')[-1]),
                    filme.find('p').text
                ) for filme in self.html.find_all('div', id='known_for')[0].find_all('li')]
        self.know = [ 
            Item(
                id=i[0],
                name=i[1], 
                tipo='filme', 
                url=f"{tmdb}/movie/{i[0]}", 
                download=False) for i in ids
            ]

def busca(item, lista):
    r = [x for x in lista if x.id == item.id]
    return len(r) > 0, r[0] if len(r) > 0 else None

def escolheAtor(atual:Filme, historico:list):
    escolhido = None
    i = 0
    while escolhido == None and i < len(atual.elenco):
        if busca(item=atual.elenco[i], lista=historico)[0] == False:
            escolhido = atual.elenco[i]
        i += 1
    return escolhido

def escolheFilme(atorAtual:Ator, historico:list):
    escolhido = None
    i = 0
    while escolhido == None and i < len(atorAtual.know):
        if busca(item=atorAtual.know[i], lista=historico)[0] == False:
            escolhido = atorAtual.know[i]
        i += 1
    return escolhido

def buscaSeq(movInit:Item, s2:Ator, seq:dict, thr:int, numMax:int=100, possivel:bool=True):
    # Possivel = True: Ainda é possivel encontrar o caminho.
    # Possivel = False: Não é mais possivel encontrar o caminho pelos atores principais.
    # Acrenscentar uma trava a cada 35 requisições, já que o site só permite 40 por segundo.
    while len(seq['historico']) < numMax and seq['encontrou'] == False and possivel:
        seq['historico'].append(Filme(url=movInit.url, thr=thr)) # Requisitar o filme e já colocar no historico.
        
        # print(f"T{thr} | FILME: {seq['historico'][-1].name}")
        encontrou, ator = busca(item=s2, lista=seq['historico'][-1].elenco)

        # Encontrou?
        if encontrou: # Sim:
            # print(f"T{thr} | {mensagem(filme=seq['historico'][-1], ator=ator)}")
            seq['historico'].append(s2)
            seq['encontrou'] = True

        else: # Não:

            # Escolher o ator entre o elenco, deve ser alguém que não esteja no historico.
            atorAtual = escolheAtor(atual=seq['historico'][-1], historico=seq['historico'])

            if atorAtual != None: # Ainda é possivel encontrar o caminho.
                seq['historico'].append(Ator(url=atorAtual.url, thr=thr))
                # print(f"T{thr} | ATOR: {seq['historico'][-1].name}")

                # Escolher o filme entre os filmes que o ator participou, deve ser um filme que não esteja no historico.
                movInit = escolheFilme(atorAtual=seq['historico'][-1], historico=seq['historico'])

            else:
                possivel = False
        # print(f"T{thr} | {len(seq['historico'])}")

    print(f"T{thr} | FIM DA THREAD | {'ENCONTRADO' if seq['encontrou'] else 'NAO ENCONTRADO'}")

def conecta(s1, s2, qntThrs=1):
    numMax = 100
    encontrou = False
    sequencias = [{'encontrou': False, 'historico': [s1]} for _ in range(qntThrs)]

    encontrados = 0
    thrs = [Thread(target=buscaSeq, args=(s1.know[i], s2, sequencias[i], i, numMax)) for i in range(qntThrs)]

    for thr in thrs:
        thr.start()

    for thr in thrs:
        thr.join()

    for seq in sequencias:
        if seq['encontrou']:
            encontrados += 1

    return sequencias, encontrados


mensagem = lambda filme, ator: f"O ator {ator.name} participou do filme {filme.name}"


# Main:
urlS1 = "https://www.themoviedb.org/person/10055-fernanda-montenegro"
urlS2 = "https://www.themoviedb.org/person/5064-meryl-streep"

s1, s2 = Ator(url=urlS1), Ator(url=urlS2)

seqs, encontrados = conecta(s1, s2, qntThrs=8)

print(f"\n\nQuantidade de caminhos encontrados: {encontrados}\n\n")


print(f"Sequencia Encontrada: ")
for seq in seqs:
    if seq['encontrou']:
        print(f"O ator {seq['historico'][0].name} fez: ")
        for item in seq['historico'][1:-2]:
            if item.tipo == 'filme':
                print(f"{item.name}")
            else:
                print(f"Onde o ator {item.name} tbm trabalhou. Além disso, ele fez parte do filme ", end='')
        print(f"Que por fim, {seq['historico'][-1].name} trabalhou.")
            
        print("\n\n")
        break