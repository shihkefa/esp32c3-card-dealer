import io
import build_cad as cad
import numpy as np

def serialize(mesh,process=True):
    data=cad.trimesh.exchange.stl.export_stl(mesh)
    return data,cad.trimesh.load_mesh(io.BytesIO(data),file_type='stl',process=process)

def as_manifold(mesh):
    solid=cad.mf.Manifold(cad.mf.Mesh(np.ascontiguousarray(mesh.vertices,dtype=np.float32),np.ascontiguousarray(mesh.faces,dtype=np.uint32)))
    assert solid.status()==cad.mf.Error.NoError,str(solid.status())
    return solid

def closed_serialization(pid,name,shape):
    source=cad.tm(shape)
    assert source.is_watertight and source.volume>0,(pid,name,'source')
    source_bodies=len(shape.m.decompose());candidate=source;steps=[]
    for attempt in range(4):
        _,actual=serialize(candidate)
        degenerate=int((~actual.nondegenerate_faces()).sum())
        steps.append({'attempt':attempt,'triangles':len(actual.faces),'watertight':bool(actual.is_watertight),'degenerate_faces':degenerate})
        if actual.is_watertight and degenerate==0:break
        # No arbitrary hole filling: require accepted quantized topology and
        # preserve every source body before another serialization attempt.
        cleaned=as_manifold(actual)
        assert len(cleaned.decompose())==source_bodies,(pid,name,'cleanup body count')
        candidate=cad.tm(cad.S(cleaned,''))
    else:
        raise RuntimeError(f'{pid} {name}: Float32 serialization did not stabilize: {steps}')
    assert actual.volume>0 and np.isfinite(actual.vertices).all(),(pid,name)
    solid=as_manifold(actual);actual_bodies=len(solid.decompose())
    assert actual_bodies==source_bodies,(pid,name,source_bodies,actual_bodies)
    ulp=float(np.spacing(np.float32(np.abs(actual.vertices).max())))
    tolerance=max(.002,4*ulp*float(source.area))
    difference=max(0.,float((shape.m-solid).volume()))+max(0.,float((solid-shape.m).volume()))
    assert difference<tolerance,(pid,name,'geometry difference',difference,tolerance)
    assert np.allclose(actual.bounds,source.bounds,atol=.001),(pid,name,'bounds')
    return actual,{'id':pid,'name':name,'source_triangles':len(source.faces),'triangles':len(actual.faces),'closed':True,'connected_bodies':actual_bodies,'source_connected_bodies':source_bodies,'float32_cleanup_applied':len(steps)>1,'serialization_attempts':steps,'symmetric_difference_mm3':difference,'float32_geometry_tolerance_mm3':tolerance}

def main():
    standard = [(pid, name, shape) for pid, name, shape, _ in cad.assembly_printables()]
    standard += [(name, name, shape) for name, shape, _ in cad.hardware if name not in {"cards", "cardedge"}]
    optional = [(pid, name, shape) for pid, name, shape, _ in cad.optional_assembly_printables()]
    optional += [(name, name, shape) for name, shape, _ in cad.P10_GRAVITY.OPTIONAL_HARDWARE]
    all_parts = standard + optional
    shift = -min(shape.m.bounding_box()[2] for _, _, shape in all_parts)
    meshes = []
    for pid, name, shape in all_parts:
        mesh, _ = closed_serialization(pid, name, shape.move(z=shift))
        meshes.append(mesh)
    version = cad.P["revision"]
    for count, filename in [(len(standard), f"發牌機_整機組裝_{version}.stl"), (len(all_parts), f"發牌機_含P10組裝_{version}.stl")]:
        mesh = cad.trimesh.util.concatenate(meshes[:count])
        path = cad.OUT / filename
        mesh.export(path)
        print(path, flush=True)

if __name__ == "__main__":
    main()
