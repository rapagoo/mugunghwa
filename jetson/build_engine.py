"""Export fixed-shape ONNX, or build a Nano-local TensorRT 8 engine (separate processes)."""
import argparse
import ast
import json
import os
from pathlib import Path

os.environ['YOLO_AUTOINSTALL'] = 'false'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['export', 'build'])
    parser.add_argument('--model', required=True, help='.pt for export; .onnx for build')
    parser.add_argument('--output', help='new .engine path for build')
    parser.add_argument('--shape', nargs=2, type=int, default=[384, 640], metavar=('HEIGHT', 'WIDTH'))
    parser.add_argument('--fp16', action='store_true')
    parser.add_argument('--workspace-mb', type=int, default=512)
    args = parser.parse_args()
    if any(s <= 0 or s % 32 for s in args.shape) or args.workspace_mb <= 0:
        parser.error('shape must be positive multiples of 32; positive workspace required')
    if args.action == 'export':
        from ultralytics import YOLO
        result = YOLO(args.model).export(format='onnx', imgsz=args.shape, batch=1, dynamic=False,
                                        opset=12, simplify=False, half=False, device=0)
        print('ONNX_EXPORTED', result, flush=True)
        return
    if not args.output or Path(args.output).exists():
        parser.error('a new --output engine path is required; existing engine is preserved')
    import onnx
    import tensorrt as trt
    if not trt.__version__.startswith('8.'):
        parser.error('this builder targets the installed TensorRT 8 API')
    logger = trt.Logger(trt.Logger.INFO)
    builder = trt.Builder(logger)
    config = builder.create_builder_config()
    config.max_workspace_size = args.workspace_mb * 1024 * 1024
    if args.fp16:
        if not builder.platform_has_fast_fp16:
            raise RuntimeError('Device reports no fast FP16 support')
        config.set_flag(trt.BuilderFlag.FP16)
    network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
    parser_onnx = trt.OnnxParser(network, logger)
    if not parser_onnx.parse_from_file(args.model):
        raise RuntimeError('\n'.join(str(parser_onnx.get_error(i)) for i in range(parser_onnx.num_errors)))
    shape = list(network.get_input(0).shape)
    if shape != [1, 3] + args.shape:
        raise RuntimeError('Unexpected ONNX input shape: ' + str(shape))
    metadata = {}
    for prop in onnx.load(args.model).metadata_props:
        try:
            metadata[prop.key] = ast.literal_eval(prop.value)
        except (ValueError, SyntaxError):
            metadata[prop.key] = prop.value
    task = metadata.get('task', 'detect')
    if task not in ('detect','pose'):
        raise RuntimeError('Only detect and pose engine exports are supported')
    if task == 'pose' and metadata.get('kpt_shape') != [17,3]:
        raise RuntimeError('Expected COCO pose keypoint shape [17,3]')
    metadata.update(imgsz=args.shape, batch=1, task=task, precision='fp16' if args.fp16 else 'fp32',
                    tensorrt_version=trt.__version__)
    print('BUILD_START', json.dumps(dict(shape=shape, fp16=args.fp16, workspace_mb=args.workspace_mb)), flush=True)
    engine = builder.build_engine(network, config)
    if engine is None:
        raise RuntimeError('TensorRT engine build failed')
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    header = json.dumps(metadata).encode('utf-8')
    with destination.open('wb') as stream:
        stream.write(len(header).to_bytes(4, 'little'))
        stream.write(header)
        stream.write(bytes(engine.serialize()))
    print('ENGINE_CREATED', str(destination), flush=True)


if __name__ == '__main__':
    main()
