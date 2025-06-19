import numpy as np
import pandas as pd
import os

out_degree_path = "../data/LiveJournal_Grid_dv/out_degree_preprocess.data"
in_degree_path = "../data/LiveJournal_Grid_dv/in_degree_preprocess.data"

print("out_degree exists:", os.path.exists(out_degree_path))
print("in_degree exists: ", os.path.exists(in_degree_path))

out_degrees = np.fromfile(out_degree_path, dtype=np.uint32)
in_degrees  = np.fromfile(in_degree_path, dtype=np.uint32)

df = pd.DataFrame({
    "vertex_id": np.arange(len(out_degrees)),
    "out_degree": out_degrees,
    "in_degree": in_degrees
})

print(f"Total vertices (out_degree): {len(out_degrees)}")
print(f"Total vertices (in_degree):  {len(in_degrees)}")
print(f"Sum of out_degrees: {out_degrees.sum()}")
print(f"Sum of in_degrees:  {in_degrees.sum()}")

print("\nFirst 10 vertices and their degrees:")
print(df.head(10))
