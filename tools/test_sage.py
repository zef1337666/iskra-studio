import torch, triton, time
from sageattention import sageattn
print("triton", triton.__version__)
q,k,v=[torch.randn(1,24,8192,128,dtype=torch.float16,device="cuda") for _ in range(3)]
o1=sageattn(q,k,v); o2=torch.nn.functional.scaled_dot_product_attention(q,k,v)
print("max diff", (o1-o2).abs().max().item(), "cos", torch.nn.functional.cosine_similarity(o1.flatten(),o2.flatten(),dim=0).item())
def bench(f):
    for _ in range(3): f()
    torch.cuda.synchronize(); t=time.time()
    for _ in range(20): f()
    torch.cuda.synchronize(); return (time.time()-t)/20*1000
print("sdpa ms", bench(lambda: torch.nn.functional.scaled_dot_product_attention(q,k,v)))
print("sage ms", bench(lambda: sageattn(q,k,v)))
