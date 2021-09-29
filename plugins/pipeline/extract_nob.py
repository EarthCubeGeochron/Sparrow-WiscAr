from pandas import read_excel, Series, concat
import numpy as N

def separate_samples(df):    
    #identify the instances of Sample: in the file
    ixs = list()
    result = df.isin(["Sample:"])
    series = result.any()
    columnNames = list(series[series == True].index)
    for col in columnNames:
        rows = list(result[col][result[col] == True].index)
        for row in rows:
            ixs.append((row, col))
    #create a dictionary to hold the dataframes for each sample        
    sdf = {}
    #fill the dicitonary
    for i in range(len(ixs)):
        try:
            sdf[i] = (df.loc[ixs[i][0]:ixs[i+1][0]-1,:]
                .dropna(axis=0, how='all')
                .dropna(axis=1, how='all'))
        except:
            sdf[i] = (df.loc[ixs[i][0]:,:]
                .dropna(axis=0, how='all')
                .dropna(axis=1, how='all'))
    return sdf

def sample_info(df):
        # Get index for the top of the Sample table
        ixa = value_index(df, "Sample:")
        ixb = value_index(df, "Material:")
        ixc = value_index(df, "Identifier:")
        sample = (df.iloc[ixa[0]:ixb[0]+1,:]
            .dropna(axis=0, how='all')
            .dropna(axis=1, how='all'))
        # Move the Identifier chunk down into the same column as Sample
        sample.at[ixb[0]+1,ixb[1]] = sample.at[ixc]
        sample.at[ixb[0]+1,ixb[1]+1] = sample.at[ixc[0],ixc[1]+1]
        sample = sample.drop([ixc[1],ixc[1]+1], axis=1)
        return(sample)

def extract_table(df):
    #get index of top of the results table
    ixb = value_index(df, "Material:")
    ixd = value_index(df, "Integrated K/Ca ±2σ")
    # Clean the table
    results = (df.loc[ixb[0]+1:ixd[0]-1,0:]
            .dropna(axis=0, how='all'))
    results.set_axis([label], axis=1, inplace=True)        
    return results

def extract_summary(df):
    #get index of top of the summary table
    ixd = value_index(df, "Integrated K/Ca ±2σ")
    try:
        ixf = value_index(df, "Notes:")
        summary = (df.loc[ixd[0]:ixf[0]-1,:]
            .dropna(axis=0, how='all')
            .dropna(axis=1, how='all'))
    except:   
        summary = (df.loc[ixd[0]:,:]
            .dropna(axis=0, how='all')
            .dropna(axis=1, how='all'))
    return summary