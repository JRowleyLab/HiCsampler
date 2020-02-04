#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import numpy as np
import argparse
import gzip
import os
from straw import straw

def kdiag(mat_dim, offset):
    '''
    The "kdiag" function is used to extract the kth diagonal co-ordinates of a square matrix 
    having the dimensions of "mat_dim" and extracting the "offset" diagonal.
    '''
    row_idx, col_idx = np.diag_indices(mat_dim)
    if offset < 0:
        return row_idx[-offset:],col_idx[:offset]
    elif offset > 0:
        return row_idx[:-offset],col_idx[offset:]
    else:
        return row_idx,col_idx
'''
"randnorm" is a function used to create a poisson distribution, centered around the varaible "read".
'''
randnorm = lambda read : np.random.poisson(int(read),1)[0]
'''
"np_randnorm" is a function created to broadcast the "randnorm" function on a NumPy array.
'''
np_randnorm = np.frompyfunc(randnorm,1,1)


# In[ ]:


class HiCPSN:
    '''
    "HiCPSN" is used to create the HiC map in NumPy matrix form.
    The size of the matrix is decided by the "chrsize" file inputted.
    The matrix is intialised by the "straw_result".
    If upsampling is performed then broadcast 1 to the entire matrix.
    Each cell in the matrix is sclaed by the given "ratio".
    '''
    def __init__(self, straw_result, chrom, ratio, res, chrsize):
        rowidxs = np.array(straw_result[0][:])/res
        colidxs = np.array(straw_result[1][:])/res
        self.scores = np.array(straw_result[2][:])
        self.nrows = int(chrsize/res)+1
        self.ncols = int(chrsize/res)+1
        print("The size of the matrix is: ", self.nrows, self.ncols)
        self.observed = np.zeros((self.nrows, self.ncols))
        for ele in range(len(self.scores)):
            self.observed[int(rowidxs[ele])][int(colidxs[ele])] = self.scores[ele]
        print("HiC Matrix Intialized for chromosome: ", chrom)
        if ratio > 1:
            self.observed = (self.observed+1)*ratio
            print("ratio is: ",ratio)
        elif 0 < ratio <= 1:
            self.observed = self.observed*ratio
            print("ratio is: ",ratio)
        del ele
        del straw_result


# In[ ]:


class HiCSampler:
    '''
    "HiCSampler" is used for randomly assiging the reads from the poisson distribution in each cell in the matrix.
    As the matrix will be symmetric, the calculations are done only on the upper triangular half of the diagonal and 
    the results are copied to the lower triangular half. The diagonals with different offests are extracted using the 
    "kdiag" function. Random assignment of reads from the poisson distribution to these diagonal elements is performed 
    using the "np_randnorm" function. To remove the effects of the 1 added to the matrix, the matrix is subtracted by the
    vlue of the "ratio".
    '''
    def __init__(self, straw_result, chrom, chrsize, ratio=1.0, res=50000):
        self.hicpsn = HiCPSN(straw_result, chrom, ratio, res, chrsize)
        self.chrom = chrom
        self.res = res
        for col in range(self.hicpsn.ncols):
            tmp = np_randnorm(np.diag(self.hicpsn.observed, col))
            self.hicpsn.observed[kdiag(self.hicpsn.ncols, col)] = tmp
            self.hicpsn.observed[kdiag(self.hicpsn.ncols, -col)] = tmp
        print("Random Poisson distribution assigned for chromosome: ", self.chrom)
        if ratio > 1:
            self.hicpsn.observed = self.hicpsn.observed-ratio
        del col
        del tmp
    
    def readShortFormattedLine(self):
        '''
        The columns just need to have
        <str1> <chr1> <pos1> <frag1> <str2> <chr2> <pos2> <frag2> <score>
        You have the chromosome, the positions, and score. The strands can just be 0, and the fragments just need to be distinct from each other i.e. frag1=1 frag2=2.
        '''
        frag1=1; frag2=2;
        chr1=self.chrom; chr2=self.chrom
        str1=0; str2=0;
        for col in range(self.hicpsn.ncols):
            diag_cords = kdiag(self.hicpsn.ncols, col)
            for ele in range(len(diag_cords[0])):
                pos1 = diag_cords[0][ele]*self.res; pos2 = diag_cords[1][ele]*self.res; score = self.hicpsn.observed[diag_cords[0][ele]][diag_cords[1][ele]]
                if score < 1:
                    continue
                yield '{0} {1} {2} {3} {4} {5} {6} {7} {8}'.format(str1, chr1, pos1, frag1, str2, chr2, pos2, frag2, score)


# In[ ]:


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-i", "--hicfile", dest="hic_file", help="Input Hi-C file (-i) or short score format files (-d)", metavar="FILE")
    group.add_argument("-d", "--dir", dest="sht_scr_dir", help=" I/p directory contatining short score format files", metavar="Directory")
    parser.add_argument("-o", "--output", dest="output", help="Creates output directory of short with score format Hi-C file for each chromosome", metavar="Output directory name", required=True)
    parser.add_argument('--ratio', dest='ratio', default=1.0, help='ratio of sub sample (ratio>1.0) will upsample/boost the input Hi-C file')
    parser.add_argument('-s', '--size', help="Input chromosome size file if i/p is HiC file (-i)", metavar="FILE")
    parser.add_argument('--res', dest='res', default = 50000, metavar='int', help="Resolution to process the Hi-C file")
    parser.add_argument('-g', dest='gzip', action='store_true', help="Output is gzipped")
    args = parser.parse_args()
    print("Entered Inputs: ", args.hic_file, args.sht_scr_dir, args.output, args.size, args.ratio, args.res)
    
    '''
    To parse through the chromosomes in .size files.
    '''        
    if not os.path.exists(args.output):
        os.mkdir(args.output)
    
    if args.hic_file:
        sizels = list()
        with open (args.size, "r") as f:
            for line in f:
                sizels.append(line.split())
        
        for chrm in sizels:
            print("Inputs to straw ",'NONE', args.hic_file, chrm[0], chrm[0], 'BP', args.res)
            result = straw('NONE', args.hic_file, chrm[0], chrm[0], 'BP', int(args.res))
            print("Processing Chromosome: ", chrm[0])
            mixer = HiCSampler(result, int(chrm[0]), ratio=float(args.ratio), res=int(args.res), chrsize=int(chrm[1]))
            file = args.output+"/chr"+chrm[0]

            if args.gzip:
                with gzip.open(file, 'wt') as f:
                    for i in mixer.readShortFormattedLine():
                        f.write(i)
                        f.write('\n')
            else: 
                with open(file, 'w+') as f:
                    for i in mixer.readShortFormattedLine():
                        f.write(i)
                        f.write('\n')
            print("Processed Chromosome: ", chrm[0])
    
    """
    To parse through the short score format files
    """
    elif args.sht_scr_dir:
        for chrfile in os.listdir(args.sht_scr_dir):
            result0 = list(); result1 = list(); result2 = list(); result = list()
            
            with open (os.path.join(args.sht_scr_dir, chrfile), "r") as f:
                for line in f:
                    line_values = line.split()
                    result0.append(int(line_values[2]))
                    result1.append(int(line_values[6]))
                    result2.append(int(float(line_values[8])))
                    chrom = int(line_values[1])
            chrsize = max(max(result0), max(result1))
            result.append(result0); result.append(result1); result.append(result2)
            print("Processing Chromosome: ", chrom)
            mixer = HiCSampler(result, chrom, ratio=float(args.ratio), res=int(args.res), chrsize=chrsize)
            file = args.output+"/chr"+str(chrom)

            if args.gzip:
                with gzip.open(file, 'wt') as f:
                    for i in mixer.readShortFormattedLine():
                        f.write(i)
                        f.write('\n')
            else: 
                with open(file, 'w+') as f:
                    for i in mixer.readShortFormattedLine():
                        f.write(i)
                        f.write('\n')

            print("Processed Chromosome: ", chrom)

