import aiohttp
import asyncio
from asyncio import Queue
import json
import pprint
import pandas as pd
import datetime
import traceback
import openpyxl
import sys
import os
import logging
import tkinter as tk
from tkinter import filedialog


logging.basicConfig(
    filename='journal_erreur.log',     # Nom du fichier de log
    level=logging.DEBUG,                # Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s | %(levelname)s | %(message)s',  # Format du message
    filemode='w'                        # 'w' pour écraser à chaque exécution, 'a' pour ajouter
)

#créer un fichier log pour les rapport sur les erreurs dans le programme(ok)
#muclé le programme pour un gestion d'erreur non bloquante
df_global=pd.DataFrame(columns=["Désignation","Image"])
nbre_code_barre_scanner=0
nbre_code_barre_nonexist=0
liste_code_barre_nonexist=[]
code_barre=""
root=tk.Tk()
root.withdraw

async def scan_code_barre(queue,stop_event):
    #mettre dans le script la possibilté de sortie du programme en arretant les scan et attendant que la pile se vide pour arreter completement le programme (ok)
    global nbre_code_barre_scanner
    global code_barre
    loop=asyncio.get_event_loop()
    while not stop_event.is_set():
        code_barre=await loop.run_in_executor(None,input,'Veuillez scanner le code barre (ou tapez "q" pour quitter):')
        if code_barre.lower()=="q":
            stop_event.set()
            print("✅ Arrêt du programme en cours")
            break
        nbre_code_barre_scanner+=1
        await queue.put(code_barre)

async def appel_API(session,url):
    #gérer les erreurs au cas par cas 
    #pas d'accès à internet problème critique mais deux cas de figures
       #au tous début du programme, pas d'accès à internet erreur critique sortie du programme
       #la erreur tourne bien,erreur momentanée d'accès à internet
    #erreur de connextion à l'API parce que clé incorrect problème critique
    try:
        async with session.get(url) as f_json:
            return await f_json.text()
    except aiohttp.ClientConnectorDNSError as e:
        logging.warning(f"Ereur DNS : {e}")
        print("Problème de pour accéder à la base de données.\n Vérifier votre connexion internet...")
        
async def extraction_donnee(f_json):
    global nbre_code_barre_nonexist
    try:
        product=json.loads(f_json)["products"][0]
        marque=product["brand"]
        libele=product['title']
        taille=product['size']
        image=product["images"][0]
        data={"marque":marque,"libélé":libele,"taille":taille,"Image":image}
        return data
    except (json.JSONDecodeError,KeyError) as e:
        if type(e).__name__=="JSONDecodeError":
            nbre_code_barre_nonexist+=1
            data=None
            print(f"Le code_bare:{code_barre}\n n'existe pas dans notre de base de donnée")
        else:
            print(f"Erreur rencontré: {e}")
        
async def traitement_code_barre(queue,api_key,session,stop_event):
    global code_barre
    while True:
        url=f"https://api.barcodelookup.com/v3/products?code-barres={code_barre}&formatted=y&clé={api_key}"
        f_json=await appel_API(session,url)
        data=await extraction_donnee(f_json)
        await enregist_fichier_excel(data,stop_event,queue)
        queue.task_done()

async def enregist_fichier_excel(data,stop_event,queue):

    global df_global
    global liste_code_barre_nonexist
    nom_fichier=f"base de produit scanné_{datetime.date.today()}.xlsx"
    if data is None:
        liste_code_barre_nonexist.append(code_barre)
    else:
        try:
            data=pd.DataFrame.from_dict(data,orient='index').T
            df_global=pd.concat([df_global,data],ignore_index=True)
        except Exception as err:
            print(f"Erreur rencontré:{err}")

        if stop_event.is_set() and queue.empty():
            
                df_global.to_excel(chemin_complet,index=True)
            else:
                df_global.to_excel(f"base de produit scanné_{datetime.date.today()}.xlsx",index=True)
        else:
            await queue.join()
            dossier_selectionne=filedialog.askdirectory("Veuillez selectionnée un Dossier pour l'enregistrement du fichier Excel")
            
            if dossier_selectionne:
                chemin_complet=os.path.join(dossier_selectionne,nom_fichier)
                df_global.to_excel(chemin_complet,index=True)
            else:
                df_global.to_excel(f"base de produit scanné_{datetime.date.today()}.xlsx",index=True)
                
            print(f"fichier sauvegarder sous le nom de: base de produit scanné_{datetime.date.today()}.xlsx")
            print("Ferméture du programme...")
            sys.exit
        

def select_fichier(nom_fichier):
    dossier_selectionne=filedialog.askdirectory(title="Veuillez selectionnée un Dossier pour l'enregistrement du fichier Excel")
    if dossier_selectionne:
        chemin_complet=os.path.join(dossier_selectionne,nom_fichier)
    else:
        


async def main():
    api_key="key"
    queue=Queue()
    stop_event=asyncio.Event()
    async with aiohttp.ClientSession() as session:
        taches=[asyncio.create_task(scan_code_barre(queue,stop_event)),asyncio.create_task(traitement_code_barre(queue,api_key,session,stop_event))]
        await asyncio.gather(*taches)

try:
    asyncio.run(main())
except BaseException as err:
    print(f"Erreur quelque part {err} type d'erreur {type(err).__name__}")
    traceback.print_exc()   

