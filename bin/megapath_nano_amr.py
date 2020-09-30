#!/usr/bin/python
import sys
import argparse 
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from shutil import copyfile
import psutil
import pysam



FLAGS=None
def process_tax_id(bam_path):
    """
    """
    try:
        acc_id_list = subprocess.check_output(
            "samtools view -@ {threads} {bam}|cut -f3|sort|uniq".format(threads=FLAGS.threads,bam=bam_path) ,encoding='utf-8',
            shell=True).strip().split("\n")
    except subprocess.CalledProcessError:
        print("No accession ID is mapped with the taxonomy ID.")
        sys.exit()
    with pysam.FastxFile(FLAGS.REFSEQ_PATH) as fin:
        for entry in fin:
            if str(entry.name) in acc_id_list:
                with open( "ref_{acc_id}.fa".format(acc_id=entry.name), mode='a') as fout, open("ref_{acc_id}.bed".format(acc_id=entry.name), mode='a') as bed_out:
                    fout.write(str(entry)+'\n')
                    bed_out.write("{name}\t0\t{end}\n".format(name=entry.name,end=len(entry.sequence)))
    with ThreadPoolExecutor(int(FLAGS.threads)) as executor:
        for acc_id in acc_id_list:
            executor.submit(process_accession_num,acc_id)

def process_accession_num(acc_id):
    """
    """
    
    copyfile("header.sam","sample_{acc_id}.sam".format(acc_id=acc_id))
    os.system("samtools view sample.sorted.bam | awk '$3 ~ /{acc_id}/' >> sample_{acc_id}.sam;" 
    "samtools view -b sample_{acc_id}.sam > sample_{acc_id}.bam;samtools index sample_{acc_id}.bam;"
    "bedtools bamtobed -i  sample_{acc_id}.bam |bedops -m - > sample_{acc_id}.merged.bed;"
    "bedops -d ref_{acc_id}.bed sample_{acc_id}.merged.bed > sample_{acc_id}.0cov.bed;"
    "bcftools mpileup -R sample_{acc_id}.merged.bed -Ou -f ref_{acc_id}.fa sample_{acc_id}.bam | bcftools call -Oz -mv -o calls_{acc_id}.vcf.gz;"
    "tabix calls_{acc_id}.vcf.gz;"
    "cat ref_{acc_id}.fa | bcftools consensus -m sample_{acc_id}.0cov.bed calls_{acc_id}.vcf.gz > cns_{acc_id}.fa".format(acc_id=acc_id,threads=FLAGS.threads))
    os.makedirs("results/{acc_id}".format(acc_id=acc_id), exist_ok=True)

    reformat_command = "gawk -F'\\t' 'NR>1 {if($1 in g){if($2>s[$8][$1]){s[$8][$1]=$2}}else {g[$8][$1]=$1; s[$8][$1]=$2};}END {for (i in g) {for (j in g[i]){fg[i]=sprintf(\"%s;%s\", fg[i], g[i][j]);fs[i]=sprintf(\"%s;%s\", fs[i],s[i][j]);}}for (i in g){if(i==\"\"){print \"Unknown \\t \" fg[i] \"\\t\" fs[i]}else {print i \"\\t \" fg[i] \"\\t\" fs[i]}}}'"

    os.makedirs("results/{acc_id}/resfinder".format(acc_id=acc_id), exist_ok=True)
    r_subprocess = subprocess.Popen('python resfinder/resfinder.py -p amr_db/resfinder/ -i cns_{acc_id}.fa -o results/{acc_id}/resfinder -t 0.90 -l 0.60 && ' 
            '{reformat_command} results/{acc_id}/resfinder/results_tab.txt > results/{acc_id}/resfinder/resf_temp.txt".format(acc_id=acc_id) && ' 
             "awk -F'\\t' -vOFS=, '{split($1,a,\", \"); for (i in a) print a[i]\"\\t\"$2\"\\t\"$3}' results/{acc_id}/resfinder/resf_temp.txt >  results/{acc_id}/resfinder/resf_temp2.txt && "  #  separate ", "
             "awk -F'\\t' -vOFS=, '{split($1,a,\"and \"); for (i in a) if(a[i]==\"\") {} else { print a[i]\"\\t\"$2\"\\t\"$3} ;}'  results/{acc_id}/resfinder/resf_temp2.txt >  results/{acc_id}/resfinder/resf.txt".format(acc_id=acc_id,reformat_command=reformat_command), shell=True)  #  separate "and "

    os.makedirs("results/{acc_id}/card".format(acc_id=acc_id), exist_ok=True)
    c_subprocess = subprocess.Popen('rgi main --input_sequence cns_{acc_id}.fa --output_file results/{acc_id}/card/results --input_type contig -n {threads} && '
        "awk -F'\t' 'NR>1{print $15 \"|\" $9 \"|\" $10}' results/{acc_id}/card/results.txt > results/{acc_id}/card/card_temp.txt && "
        "awk -F'|' -vOFS=, '{split($1,a,\"; \"); for (i in a) if(a[i] !~ /antibiotic/){print a[i]\"|\"$2\"|\"$3} else {split(a[i],b,\" \"); print b[1]\"|\"$2\"|\"$3} ;}' results/{acc_id}/card/card_temp.txt > results/{acc_id}/card/card.txt".format(acc_id=acc_id,threads=FLAGS.threads), shell=True)


    os.makedirs("results/{acc_id}/amrfinder".format(acc_id=acc_id), exist_ok=True )
    add_flag=''
    if FLAGS.taxon != '':
        add_flag='-O '+FLAGS.taxon
    a_subprocess = subprocess.Popen('amrfinder {add_flag} -n cns_{acc_id}.fa > results/{acc_id}/amrfinder/results.txt && ' 
                "awk -F'\\t' 'NR>1{print $12 \"\\t\" $6 \"\\t\" $17}' results/{acc_id}/amrfinder/results.txt > results/{acc_id}/amrfinder/amrf_temp.txt && " 
                "awk -F'\\t' -vOFS=, '{split($1,a,\"; \"); for (i in a) if(a[i] !~ /antibiotic/){print a[i]\"\\t\"$2\"\\t\"$3} else {split(a[i],b,\" \"); print b[1]\"\\t\"$2\"\\t\"$3} ;}' results/{acc_id}/amrfinder/amrf_temp.txt > results/{acc_id}/amrfinder/amrf.txt".format(add_flag=add_flag,acc_id=acc_id), shell=True)
    os.makedirs("results/{acc_id}/megares".format(acc_id=acc_id), exist_ok=True )
    m_subprocess = subprocess.Popen('python blast_amr.py -i cns_{acc_id}.fa -o results/{acc_id}/megares/ -d megares_database_v1.01_AMRDetection -p amr_db/megares_db -l 0.9 -t 0.6  && ' 
            '{reformat_command} results/{acc_id}/megares/results_tab.txt > results/{acc_id}/megares/megares.txt'.format(acc_id=acc_id,reformat_command=reformat_command), shell=True)

    os.makedirs("results/{acc_id}/cbmar".format(acc_id=acc_id), exist_ok=True )
    cbmar_subprocess = subprocess.Popen('python blast_amr.py -i cns_{acc_id}.fa -o results/{acc_id}/cbmar/ -d cbmar -p amr_db/cbmar -l 0.9 -t 0.6  && ' 
            '{reformat_command} results/{acc_id}/cbmar/results_tab.txt > results/{acc_id}/cbmar/cbmar.txt'.format(acc_id=acc_id,reformat_command=reformat_command), shell=True)

    r_subprocess.communicate()
    c_subprocess.communicate()
    a_subprocess.communicate()
    m_subprocess.communicate()
    cbmar_subprocess.communicate()


def merge_results(dir_arr):
    #TODO threading
    """
    consolidating the results of all accession IDs
    :param dir_arr:
    :return:
    """
    card_acc_id = {}
    card_gene = {}
    card_score = {}

    resf_acc_id = {}
    resf_gene = {}
    resf_score = {}

    amrf_acc_id = {}
    amrf_gene = {}
    amrf_score = {}

    mega_acc_id = {}
    mega_gene = {}
    mega_score = {}

    cbmar_acc_id = {}
    cbmar_gene = {}
    cbmar_score = {}

    for acc_id in dir_arr:
        acc_id = acc_id[:-1]  #removing slash

        card = []
        if os.path.isfile("{acc_id}/card/card.txt".format(acc_id=acc_id)) and os.path.getsize("{acc_id}/card/card.txt".format(acc_id=acc_id)):
            card = subprocess.check_output("cat {acc_id}/card/card.txt".format(acc_id=acc_id),encoding='utf-8', shell=True).strip().split("\n")

        for rec in card:
            
            #col = rec.split("\t")
            col = rec.split("|")
            cdrug = col[0].strip()
            if cdrug not in card_acc_id:
                card_acc_id[cdrug] = acc_id
                card_gene[cdrug] = col[1]
                card_score[cdrug] = col[2]
            else:
                if acc_id not in card_acc_id[cdrug]:
                    card_acc_id[cdrug] = card_acc_id[cdrug] + "|" + acc_id
                    card_gene[cdrug] = card_gene[cdrug] + "|"
                    card_score[cdrug] = card_score[cdrug] + "|"
                if card_gene[cdrug][-1] != "|":
                    card_gene[cdrug] = card_gene[cdrug] + ";" + col[1]
                    card_score[cdrug] = card_score[cdrug] + ";" + col[2]
                elif card_gene[cdrug][-1] == "|":
                    card_gene[cdrug] = card_gene[cdrug] + col[1]
                    card_score[cdrug] = card_score[cdrug] + col[2]

        resf = []
        if os.path.isfile("{acc_id}/resfinder/resf.txt".format(acc_id=acc_id)) and os.path.getsize("{acc_id}/resfinder/resf.txt".format(acc_id=acc_id)):
            resf = subprocess.check_output("cat {acc_id}/resfinder/resf.txt".format(acc_id=acc_id),encoding='utf-8', shell=True).strip().split("\n")
        for rec in resf:
            
            col = rec.split("\t")
            rdrug_arr = col[0].split(" resistance")
            rdrug = rdrug_arr[0]
            rdrug = rdrug.lower().strip()
            if rdrug.endswith('s'):
                rdrug = rdrug[:-1]
            # merge drugs if multiple entries
            if rdrug not in resf_acc_id:
                resf_acc_id[rdrug] = acc_id
                resf_gene[rdrug] = col[1]
                resf_score[rdrug] = col[2]
            else:
                if acc_id not in resf_acc_id[rdrug]:
                    resf_acc_id[rdrug] = resf_acc_id[rdrug] + "|" + acc_id
                    resf_gene[rdrug] = resf_gene[rdrug] + "|"
                    resf_score[rdrug] = resf_score[rdrug] + "|"

                if col[1].strip() != "":
                    if resf_gene[rdrug][-1] != "|":
                        resf_gene[rdrug] = resf_gene[rdrug] + ";" + col[1]
                        resf_score[rdrug] = resf_score[rdrug] + ";" + col[2]
                    elif resf_gene[rdrug][-1] == "|":
                        resf_gene[rdrug] = resf_gene[rdrug] + col[1]
                        resf_score[rdrug] = resf_score[rdrug] + col[2]
        mega=[]
        if os.path.isfile("{acc_id}/megares/megares.txt".format(acc_id=acc_id)) and os.path.getsize("{acc_id}/megares/megares.txt".format(acc_id=acc_id)):
            mega = subprocess.check_output("cat {acc_id}/megares/megares.txt".format(acc_id=acc_id),encoding='utf-8', shell=True).strip().split("\n")
        for rec in mega:
            
            col = rec.split("\t")
            mdrug = col[0]
            mdrug = mdrug.lower().strip()
            if mdrug.endswith('s'):
                mdrug = mdrug[:-1]
            # merge drugs if multiple entries
            if mdrug not in mega_acc_id:
                mega_acc_id[mdrug] = acc_id
                mega_gene[mdrug] = col[1]
                mega_score[mdrug] = col[2].strip()
            else:
                if acc_id not in mega_acc_id[mdrug]:
                    mega_acc_id[mdrug] = mega_acc_id[mdrug] + "|" + acc_id
                    mega_gene[mdrug] = mega_gene[mdrug] + "|"
                    mega_score[mdrug] = mega_score[mdrug] + "|"

                if col[1].strip() != "":
                    if mega_gene[mdrug][-1] != "|":
                        mega_gene[mdrug] = mega_gene[mdrug] + ";" + col[1]
                        mega_score[mdrug] = mega_score[mdrug] + ";" + col[2].strip()
                    elif mega_gene[mdrug][-1] == "|":
                        mega_gene[mdrug] = mega_gene[mdrug] + col[1]
                        mega_score[mdrug] = mega_score[mdrug] + col[2].strip()
        
        cbmar=[]
        if os.path.isfile("{acc_id}/cbmar/cbmar.txt".format(acc_id=acc_id)) and os.path.getsize("{acc_id}/cbmar/cbmar.txt".format(acc_id=acc_id)):
            cbmar = subprocess.check_output("cat {acc_id}/cbmar/cbmar.txt".format(acc_id=acc_id),encoding='utf-8', shell=True).strip().split("\n")
        for rec in cbmar:
            
            col = rec.split("\t")
            cbmardrug = col[0]
            cbmardrug = cbmardrug.lower().strip()
            if cbmardrug.endswith('s'):
                cbmardrug = cbmardrug[:-1]
            # merge drugs if multiple entries
            if cbmardrug not in cbmar_acc_id:
                cbmar_acc_id[cbmardrug] = acc_id
                cbmar_gene[cbmardrug] = col[1]
                cbmar_score[cbmardrug] = col[2].strip()
            else:
                if acc_id not in cbmar_acc_id[cbmardrug]:
                    cbmar_acc_id[cbmardrug] = cbmar_acc_id[cbmardrug] + "|" + acc_id
                    cbmar_gene[cbmardrug] = cbmar_gene[cbmardrug] + "|"
                    cbmar_score[cbmardrug] = cbmar_score[cbmardrug] + "|"

                if col[1].strip() != "":
                    if cbmar_gene[cbmardrug][-1] != "|":
                        cbmar_gene[cbmardrug] = cbmar_gene[cbmardrug] + ";" + col[1]
                        cbmar_score[cbmardrug] = cbmar_score[cbmardrug] + ";" + col[2].strip()
                    elif cbmar_gene[cbmardrug][-1] == "|":
                        cbmar_gene[cbmardrug] = cbmar_gene[cbmardrug] + col[1]
                        cbmar_score[cbmardrug] = cbmar_score[cbmardrug] + col[2].strip()



        # merge the amrfinder results:
        amrf = []
        if os.path.isfile("{acc_id}/amrfinder/amrf.txt".format(acc_id=acc_id)) and os.path.getsize("{acc_id}/amrfinder/amrf.txt".format(acc_id=acc_id)):
            amrf = subprocess.check_output("cat {acc_id}/amrfinder/amrf.txt".format(acc_id=acc_id),encoding='utf-8', shell=True).strip().split("\n")
        for rec in amrf:
            
            col = rec.split("\t")
            adrug = col[0].strip().lower()
            if adrug not in amrf_acc_id:
                amrf_acc_id[adrug] = acc_id
                amrf_gene[adrug] = col[1]
                amrf_score[adrug] = col[2].strip()
            else:
                if acc_id not in amrf_acc_id[adrug]:
                    amrf_acc_id[adrug] = amrf_acc_id[adrug] + "|" + acc_id
                    amrf_gene[adrug] = amrf_gene[adrug] + "|"
                    amrf_score[adrug] = amrf_score[adrug] + "|"
                if amrf_gene[adrug][-1] != "|":
                    amrf_gene[adrug] = amrf_gene[adrug] + ";" + col[1]
                    amrf_score[adrug] = amrf_score[adrug] + ";" + col[2].strip()
                elif amrf_gene[adrug][-1] == "|":
                    amrf_gene[adrug] = amrf_gene[adrug] + col[1]
                    amrf_score[adrug] = amrf_score[adrug] + col[2].strip()



    # output results
    with open("results.txt", "w") as f:
        f.write(". \t resfinder \t . \t . \t CARD \t . \t . \t megares \t . \t . \t cbmar \t . \t . \t amrfinder \t . \t . \t \n")
        f.write(
            "Antibiotics Ineffective to Bacteria \t AccessionIDs \t Genes \t IDscore \t AccessionIDs \t Genes \t IDscore \t AccessionIDs \t Genes \t IDscore \t AccessionIDs \t Genes \t IDscore \t AccessionIDs \t Genes \t IDscore \n")

        for key in card_acc_id:
            if key not in resf_acc_id and key not in mega_acc_id and key not in cbmar_acc_id and key not in amrf_acc_id:
                f.write("%s\t.\t.\t.\t%s\t%s\t%s\t.\t.\t.\t.\t.\t.\t.\t.\t.\n" % (
                    key, card_acc_id[key], card_gene[key], card_score[key]))
            elif key not in resf_acc_id and key not in mega_acc_id and key not in cbmar_acc_id and key in amrf_acc_id:
                f.write("%s\t.\t.\t.\t%s\t%s\t%s\t.\t.\t.\t.\t.\t.\t%s\t%s\t%s\n" % (
                    key,  card_acc_id[key], card_gene[key], card_score[key],amrf_acc_id[key],amrf_gene[key],amrf_score[key]))

            elif key in resf_acc_id and key not in mega_acc_id and key not in cbmar_acc_id and key not in amrf_acc_id:
                f.write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t.\t.\t.\t.\t.\t.\t.\t.\t.\n" % (
                    key, resf_acc_id[key], resf_gene[key], resf_score[key], card_acc_id[key], card_gene[key], card_score[key]))
            elif key in resf_acc_id and key not in mega_acc_id and key not in cbmar_acc_id and key in amrf_acc_id:
                f.write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t.\t.\t.\t.\t.\t.\t%s\t%s\t%s\n" % (
                    key,  resf_acc_id[key], resf_gene[key], resf_score[key],card_acc_id[key], card_gene[key], card_score[key],amrf_acc_id[key],amrf_gene[key],amrf_score[key]))

            elif key not in resf_acc_id and key in mega_acc_id and key not in cbmar_acc_id and key not in amrf_acc_id:
                f.write("%s\t.\t.\t.\t%s\t%s\t%s\t%s\t%s\t%s\t.\t.\t.\t.\t.\t.\n" % (
                    key, card_acc_id[key], card_gene[key], card_score[key], mega_acc_id[key], mega_gene[key], mega_score[key]))
            elif key not in resf_acc_id and key in mega_acc_id and key not in cbmar_acc_id and key in amrf_acc_id:
                f.write("%s\t.\t.\t.\t%s\t%s\t%s\t%s\t%s\t%s\t.\t.\t.\t%s\t%s\t%s\n" % (
                    key,  card_acc_id[key], card_gene[key], card_score[key],mega_acc_id[key], mega_gene[key], mega_score[key],amrf_acc_id[key],amrf_gene[key],amrf_score[key]))

            elif key in resf_acc_id and key in mega_acc_id and key not in cbmar_acc_id and key not in amrf_acc_id:
                f.write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t.\t.\t.\t.\t.\t.\n" % (
                    key, resf_acc_id[key], resf_gene[key], resf_score[key], card_acc_id[key], card_gene[key], card_score[key], mega_acc_id[key], mega_gene[key], mega_score[key]))
            elif key in resf_acc_id and key in mega_acc_id and key not in cbmar_acc_id and key in amrf_acc_id:
                f.write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t.\t.\t.\t%s\t%s\t%s\n" % (
                    key,  resf_acc_id[key], resf_gene[key], resf_score[key],card_acc_id[key], card_gene[key], card_score[key],mega_acc_id[key], mega_gene[key], mega_score[key],amrf_acc_id[key],amrf_gene[key],amrf_score[key]))

            elif key in resf_acc_id and key in mega_acc_id and key in cbmar_acc_id and key not in amrf_acc_id:
                f.write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t.\t.\t.\n" % (
                    key, resf_acc_id[key], resf_gene[key], resf_score[key], card_acc_id[key], card_gene[key], card_score[key], mega_acc_id[key], mega_gene[key], mega_score[key],cbmar_acc_id[key],cbmar_gene[key],cbmar_score[key]))
            elif key in resf_acc_id and key in mega_acc_id and key in cbmar_acc_id and key in amrf_acc_id:
                f.write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" % (
                    key,  resf_acc_id[key], resf_gene[key], resf_score[key],card_acc_id[key], card_gene[key], card_score[key],mega_acc_id[key], mega_gene[key], mega_score[key],cbmar_acc_id[key],cbmar_gene[key],cbmar_score[key],amrf_acc_id[key],amrf_gene[key],amrf_score[key]))

            elif key not in resf_acc_id and key in mega_acc_id and key in cbmar_acc_id and key not in amrf_acc_id:
                f.write("%s\t.\t.\t.\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t.\t.\t.\n" % (
                    key, card_acc_id[key], card_gene[key], card_score[key], mega_acc_id[key], mega_gene[key], mega_score[key],cbmar_acc_id[key],cbmar_gene[key],cbmar_score[key]))
            elif key not in resf_acc_id and key in mega_acc_id and key in cbmar_acc_id and key in amrf_acc_id:
                f.write("%s\t.\t.\t.\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" % (
                    key,  card_acc_id[key], card_gene[key], card_score[key], mega_acc_id[key], mega_gene[key], mega_score[key],cbmar_acc_id[key],cbmar_gene[key],cbmar_score[key],amrf_acc_id[key],amrf_gene[key],amrf_score[key]))

            elif key in resf_acc_id and key not in mega_acc_id and key in cbmar_acc_id and key not in amrf_acc_id:
                f.write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t.\t.\t.\t%s\t%s\t%s\t.\t.\t.\n" % (
                    key, resf_acc_id[key], resf_gene[key], resf_score[key], card_acc_id[key], card_gene[key], card_score[key],cbmar_acc_id[key],cbmar_gene[key],cbmar_score[key]))
            elif key in resf_acc_id and key not in mega_acc_id and key in cbmar_acc_id and key in amrf_acc_id:
                f.write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t.\t.\t.\t%s\t%s\t%s\t%s\t%s\t%s\n" % (
                    key,  resf_acc_id[key], resf_gene[key], resf_score[key],card_acc_id[key], card_gene[key], card_score[key],cbmar_acc_id[key],cbmar_gene[key],cbmar_score[key],amrf_acc_id[key],amrf_gene[key],amrf_score[key]))
            elif key not in resf_acc_id and key not in mega_acc_id and key in cbmar_acc_id and key not in amrf_acc_id:
                f.write("%s\t.\t.\t.\t%s\t%s\t%s\t.\t.\t.\t%s\t%s\t%s\t.\t.\t.\n" % (
                    key,  card_acc_id[key], card_gene[key], card_score[key],cbmar_acc_id[key],cbmar_gene[key],cbmar_score[key]))
            elif key not in resf_acc_id and key not in mega_acc_id and key in cbmar_acc_id and key in amrf_acc_id:
                f.write("%s\t.\t.\t.\t%s\t%s\t%s\t.\t.\t.\t%s\t%s\t%s\t%s\t%s\t%s\n" % (
                    key,  card_acc_id[key], card_gene[key], card_score[key],cbmar_acc_id[key],cbmar_gene[key],cbmar_score[key],amrf_acc_id[key],amrf_gene[key],amrf_score[key]))

        for key in resf_acc_id:
            if key not in card_acc_id and key not in mega_acc_id and key not in cbmar_acc_id and key not in amrf_acc_id:
                f.write("%s\t%s\t%s\t%s\t.\t.\t.\t.\t.\t.\t.\t.\t.\t.\t.\t.\n" % (key, resf_acc_id[key], resf_gene[key], resf_score[key]))
            elif key not in card_acc_id and key not in mega_acc_id and key not in cbmar_acc_id and key in amrf_acc_id:
                f.write("%s\t%s\t%s\t%s\t.\t.\t.\t.\t.\t.\t.\t.\t.\t%s\t%s\t%s\n" % (key, resf_acc_id[key], resf_gene[key], resf_score[key],amrf_acc_id[key],amrf_gene[key],amrf_score[key]))

            elif key not in card_acc_id and key in mega_acc_id and key not in cbmar_acc_id and key not in amrf_acc_id:
                f.write("%s\t%s\t%s\t%s\t.\t.\t.\t%s\t%s\t%s\t.\t.\t.\t.\t.\t.\n" % (key, resf_acc_id[key], resf_gene[key], resf_score[key], mega_acc_id[key], mega_gene[key], mega_score[key]))
            elif key not in card_acc_id and key in mega_acc_id and key not in cbmar_acc_id and key in amrf_acc_id:
                f.write("%s\t%s\t%s\t%s\t.\t.\t.\t%s\t%s\t%s\t.\t.\t.\t%s\t%s\t%s\n" % (key, resf_acc_id[key], resf_gene[key], resf_score[key], mega_acc_id[key], mega_gene[key], mega_score[key],amrf_acc_id[key],amrf_gene[key],amrf_score[key]))


            elif key not in card_acc_id and key in mega_acc_id and key in cbmar_acc_id and key not in amrf_acc_id:
                f.write("%s\t%s\t%s\t%s\t.\t.\t.\t%s\t%s\t%s\t%s\t%s\t%s\t.\t.\t.\n" % (key, resf_acc_id[key], resf_gene[key], resf_score[key], mega_acc_id[key], mega_gene[key], mega_score[key],cbmar_acc_id[key],cbmar_gene[key],cbmar_score[key]))
            elif key not in card_acc_id and key in mega_acc_id and key in cbmar_acc_id and key in amrf_acc_id:
                f.write("%s\t%s\t%s\t%s\t.\t.\t.\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" % (key, resf_acc_id[key], resf_gene[key], resf_score[key], mega_acc_id[key], mega_gene[key], mega_score[key],cbmar_acc_id[key],cbmar_gene[key],cbmar_score[key],amrf_acc_id[key],amrf_gene[key],amrf_score[key]))


            elif key not in card_acc_id and key not in mega_acc_id and key in cbmar_acc_id and key not in amrf_acc_id:
                f.write("%s\t%s\t%s\t%s\t.\t.\t.\t.\t.\t.\t%s\t%s\t%s\t.\t.\t.\n" % (key, resf_acc_id[key], resf_gene[key], resf_score[key], cbmar_acc_id[key],cbmar_gene[key],cbmar_score[key]))
            elif key not in card_acc_id and key not in mega_acc_id and key in cbmar_acc_id and key in amrf_acc_id:
                f.write("%s\t%s\t%s\t%s\t.\t.\t.\t.\t.\t.\t%s\t%s\t%s\t%s\t%s\t%s\n" % (key, resf_acc_id[key], resf_gene[key], resf_score[key], cbmar_acc_id[key],cbmar_gene[key],cbmar_score[key],amrf_acc_id[key],amrf_gene[key],amrf_score[key]))

        for key in mega_acc_id:
            if key not in card_acc_id and key not in resf_acc_id and key not in cbmar_acc_id and key not in amrf_acc_id:
                f.write("%s\t.\t.\t.\t.\t.\t.\t%s\t%s\t%s\t.\t.\t.\t.\t.\t.\n" % (key, mega_acc_id[key], mega_gene[key], mega_score[key]))
            elif key not in card_acc_id and key not in resf_acc_id and key not in cbmar_acc_id and key in amrf_acc_id:
                f.write("%s\t.\t.\t.\t.\t.\t.\t%s\t%s\t%s\t.\t.\t.\t%s\t%s\t%s\n" % (key, mega_acc_id[key], mega_gene[key], mega_score[key],amrf_acc_id[key],amrf_gene[key],amrf_score[key]))


            elif key not in card_acc_id and key not in resf_acc_id and key in cbmar_acc_id and key not in amrf_acc_id:
                f.write("%s\t.\t.\t.\t.\t.\t.\t%s\t%s\t%s\t%s\t%s\t%s\t.\t.\t.\n" % (key, mega_acc_id[key], mega_gene[key], mega_score[key], cbmar_acc_id[key],cbmar_gene[key],cbmar_score[key]))
            elif key not in card_acc_id and key not in resf_acc_id and key in cbmar_acc_id and key in amrf_acc_id:
                f.write("%s\t.\t.\t.\t.\t.\t.\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" % (key, mega_acc_id[key], mega_gene[key], mega_score[key],cbmar_acc_id[key],cbmar_gene[key],cbmar_score[key],amrf_acc_id[key],amrf_gene[key],amrf_score[key]))


        for key in cbmar_acc_id:
            if key not in card_acc_id and key not in resf_acc_id and key not in mega_acc_id and key not in amrf_acc_id:
                f.write("%s\t.\t.\t.\t.\t.\t.\t.\t.\t.\t%s\t%s\t%s\t.\t.\t.\n" % (key, cbmar_acc_id[key],cbmar_gene[key],cbmar_score[key]))
            elif key not in card_acc_id and key not in resf_acc_id and key not in cbmar_acc_id and key in amrf_acc_id:
                f.write("%s\t.\t.\t.\t.\t.\t.\t.\t.\t.\t%s\t%s\t%s\t%s\t%s\t%s\n" % (key, cbmar_acc_id[key],cbmar_gene[key],cbmar_score[key],amrf_acc_id[key],amrf_gene[key],amrf_score[key]))
        for key in amrf_acc_id:
            if key not in card_acc_id and key not in resf_acc_id and key not in mega_acc_id and key not in cbmar_acc_id:
                f.write("%s\t.\t.\t.\t.\t.\t.\t.\t.\t.\t.\t.\t.\t%s\t%s\t%s\n" % (key, amrf_acc_id[key],amrf_gene[key],amrf_score[key]))

            
def main():
    os.makedirs(FLAGS.output_folder,exist_ok=True)
    bam_path = os.path.abspath(FLAGS.query_bam)
    os.chdir(FLAGS.output_folder)
    print("current directory: " + os.getcwd())

    if not os.path.exists("sample.sorted.bam") or not os.path.exists("sample.sorted.bam.bai") or not os.path.exists("header.sam") :
        os.system("samtools sort {bam_path} -o sample.sorted.bam;" 
                "samtools index sample.sorted.bam;"
                "samtools view -@ {threads} -H sample.sorted.bam > header.sam".format(bam_path=bam_path,threads=FLAGS.threads))

    # make the output directory
    os.makedirs("results",exist_ok=True)
    
    process_tax_id(bam_path)

    print("All results have been generated")
    os.chdir("results")
    print("current directory " + os.getcwd())

    try:
        dir_arr = next(os.walk('.'), ([],[],[]))[1]
    except subprocess.CalledProcessError:
        print("No accession ID is mapped with the sequence ID in bam.")
    else:
        print("Processing results of: {acc_list}".format(acc_list=", ".join(dir_arr)))
        merge_results(dir_arr)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MegaPath-Nano: AMR Detection') 
    parser.add_argument('--query_bam', required=True,help='Input bam')
    parser.add_argument('--output_folder', required=True,help='Output directory')
    parser.add_argument('--taxon', help='Taxon-specific options for AMRFinder, curated organisms: Campylobacter, Enterococcus_faecalis, Enterococcus_faecium, Escherichia, Klebsiella, Salmonella, Staphylococcus_aureus, Staphylococcus_pseudintermedius, Vibrio_cholerae')
    parser.add_argument('--threads', default=psutil.cpu_count(logical=True), help='Num of threads')
    CWD=os.path.dirname(os.path.realpath(__file__))
    NANO_DIR=os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    parser.add_argument('--REFSEQ_PATH', default='%s/genomes/refseq/refseq.fna'%(NANO_DIR), help='The path of RefSeq')
    FLAGS = parser.parse_args()
    main()