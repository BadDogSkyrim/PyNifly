"""Layouts of the hk_2014 classes in FO4 cloth (BSClothExtraData), for pyn/hk2014_graph.py.

FO4's cloth packfiles carry no type section, so these were worked out from the 146 vanilla nifs
with cloth (2026-11-26; scripts in the phase 7 work folder) and checked by reading and writing
every vanilla blob byte for byte (TEST_FO4_CLOTH_GRAPH_ROUNDTRIP). Field names follow Havok's
where known.

A layout is (size, [(offset, name, type)]). Types:
    'u8' 'i8' 'u16' 'i16' 'u32' 'i32' 'f32'     scalars
    'vec4'                                      4 floats
    'mat4'                                      16 floats, column-major
    'str'                                       hkStringPtr (local fixup to inline chars)
    'ptr'                                       pointer to another object (global fixup)
    ('arr', T)                                  hkArray<T>: data written after the object
    ('fixed', T, n)                             n of T, inline
    ('struct', Name)                            an inline STRUCTS[Name]
Bytes no field covers are zero in every vanilla blob; the reader checks that.
"""

# Class signatures, as every vanilla __classnames__ section gives them.
SIGNATURES = {
    'hkClass': 0x33D42383, 'hkClassMember': 0xB0EFA719, 'hkClassEnum': 0x8A3609CF,
    'hkClassEnumItem': 0xCE6F8A6C,
    'hkRootLevelContainer': 661831966, 'hclClothData': 4181970594,
    'hclSimClothData': 3859829127, 'hclCollidable': 4047530174,
    'hclTaperedCapsuleShape': 3752169249, 'hclCapsuleShape': 3708024100,
    'hclStandardLinkConstraintSet': 1114321748, 'hclStretchLinkConstraintSet': 1114321748,
    'hclLocalRangeConstraintSet': 2186704901, 'hclBendStiffnessConstraintSet': 288448265,
    'hclBendLinkConstraintSet': 646072151, 'hclCompressibleLinkConstraintSet': 1374147701,
    'hclBonePlanesConstraintSet': 1522845641, 'hclVolumeConstraintMx': 58032882,
    'hclSimClothPose': 455429281, 'hclScratchBufferDefinition': 2685602348,
    'hclBufferDefinition': 2135579644, 'hclTransformSetDefinition': 419251557,
    'hclObjectSpaceSkinPNOperator': 2219346838, 'hclMoveParticlesOperator': 3864686620,
    'hclSimulateOperator': 1975987983, 'hclSimpleMeshBoneDeformOperator': 2161735327,
    'hclCopyVerticesOperator': 3873113932, 'hclGatherAllVerticesOperator': 3664999062,
    'hclGatherSomeVerticesOperator': 2237234416, 'hclClothState': 2063781147,
    'hkaSkeleton': 4274114267,
}

_OP = [(16, 'name', 'str'), (24, 'operatorID', 'u32')]
_CS = [(16, 'name', 'str'), (24, 'constraintId', 'u32')]


def _blend(n):
    return (32 + 32 * n + (16 * n if n > 1 else 0),
            [(0, 'vertexIndices', ('fixed', 'u16', 16)),
             (32, 'boneIndices', ('fixed', 'u16', 16 * n))]
            + ([(32 + 32 * n, 'boneWeights', ('fixed', 'u8', 16 * n))] if n > 1 else []))


STRUCTS = {
    'NamedVariant': (24, [(0, 'name', 'str'), (8, 'className', 'str'), (16, 'variant', 'ptr')]),
    'ParticleData': (16, [(0, 'mass', 'f32'), (4, 'invMass', 'f32'), (8, 'radius', 'f32'),
                          (12, 'friction', 'f32')]),
    'PinchData': (8, [(0, 'pinchDetectionEnabled', 'u8'), (1, 'pinchDetectionPriority', 'i8'),
                      (4, 'pinchDetectionRadius', 'f32')]),
    'Link': (12, [(0, 'particleA', 'u16'), (2, 'particleB', 'u16'), (4, 'restLength', 'f32'),
                  (8, 'stiffness', 'f32')]),
    'BendStiffnessLink': (32, [(0, 'weightA', 'f32'), (4, 'weightB', 'f32'),
                               (8, 'weightC', 'f32'), (12, 'weightD', 'f32'),
                               (16, 'bendStiffness', 'f32'), (20, 'restCurvature', 'f32'),
                               (24, 'particleA', 'u16'), (26, 'particleB', 'u16'),
                               (28, 'particleC', 'u16'), (30, 'particleD', 'u16')]),
    'BendLink': (20, [(0, 'particleA', 'u16'), (2, 'particleB', 'u16'),
                      (4, 'bendMinLength', 'f32'), (8, 'stretchMaxLength', 'f32'),
                      (12, 'bendStiffness', 'f32'), (16, 'stretchStiffness', 'f32')]),
    'CompressibleLink': (16, [(0, 'particleA', 'u16'), (2, 'particleB', 'u16'),
                              (4, 'restLength', 'f32'), (8, 'compressionLength', 'f32'),
                              (12, 'stiffness', 'f32')]),
    'LocalConstraint': (16, [(0, 'particleIndex', 'u16'), (2, 'referenceVertex', 'u16'),
                             (4, 'maximumDistance', 'f32'), (8, 'maxNormalDistance', 'f32'),
                             (12, 'minNormalDistance', 'f32')]),
    'BonePlane': (32, [(0, 'planeEquationBone', 'vec4'), (16, 'particleIndex', 'u16'),
                       (18, 'transformIndex', 'u16'), (20, 'stiffness', 'f32')]),
    'FrameBatch': (352, [(0, 'frameVector', ('fixed', 'vec4', 16)),
                         (256, 'particleIndex', ('fixed', 'u16', 16)),
                         (288, 'weight', ('fixed', 'f32', 16))]),
    'FrameSingle': (32, [(0, 'frameVector', 'vec4'), (16, 'particleIndex', 'u16'),
                         (20, 'weight', 'f32')]),
    'ApplyBatch': (352, [(0, 'frameVector', ('fixed', 'vec4', 16)),
                         (256, 'particleIndex', ('fixed', 'u16', 16)),
                         (288, 'stiffness', ('fixed', 'f32', 16))]),
    'ApplySingle': (32, [(0, 'frameVector', 'vec4'), (16, 'particleIndex', 'u16'),
                         (20, 'stiffness', 'f32')]),
    'FourBlend': _blend(4), 'ThreeBlend': _blend(3), 'TwoBlend': _blend(2),
    'OneBlend': _blend(1),
    'LocalPN': (256, [(0, 'localPosition', ('fixed', 'i16', 64)),
                      (128, 'localNormal', ('fixed', 'i16', 64))]),
    'VertexParticlePair': (4, [(0, 'vertexIndex', 'u16'), (2, 'particleIndex', 'u16')]),
    'TriangleBonePair': (4, [(0, 'boneOffset', 'u16'), (2, 'triangleOffset', 'u16')]),
    'VertexPair': (4, [(0, 'indexInput', 'u16'), (2, 'indexOutput', 'u16')]),
    'BufferAccess': (16, [(0, 'bufferIndex', 'u32'), (4, 'bufferUsage', ('fixed', 'u8', 5)),
                          (12, 'shadowBufferIndex', 'u32')]),
    'BitField': (24, [(0, 'words', ('arr', 'u32')), (16, 'numBits', 'i32')]),
    'TransformTracker': (72, [(0, 'read', ('struct', 'BitField')),
                              (24, 'readBeforeWrite', ('struct', 'BitField')),
                              (48, 'written', ('struct', 'BitField'))]),
    'TransformSetAccess': (32, [(0, 'transformSetIndex', 'u32'),
                                (8, 'perComponentFlags', ('fixed', 'u8', 2)),
                                (16, 'perComponentTransformTrackers',
                                 ('arr', ('struct', 'TransformTracker')))]),
    'Bone': (16, [(0, 'name', 'str'), (8, 'lockTranslation', 'u8')]),
    'QsTransform': (48, [(0, 'translation', 'vec4'), (16, 'rotation', 'vec4'),
                         (32, 'scale', 'vec4')]),
    'BufferLayout': (26, [(0, 'elementsLayout', ('fixed', 'u8', 16)),
                          (16, 'slots', ('fixed', 'u8', 8)),
                          (24, 'numSlots', 'u8'), (25, 'triangleFormat', 'u8')]),
}


def _s(name):
    return ('arr', ('struct', name))


CLASSES = {
    'hkRootLevelContainer': (16, [(0, 'namedVariants', _s('NamedVariant'))]),
    'hclClothData': (128, [(16, 'name', 'str'), (24, 'simClothDatas', ('arr', 'ptr')),
                           (40, 'bufferDefinitions', ('arr', 'ptr')),
                           (56, 'transformSetDefinitions', ('arr', 'ptr')),
                           (72, 'operators', ('arr', 'ptr')),
                           (88, 'clothStateDatas', ('arr', 'ptr')),
                           (104, 'actions', ('arr', 'ptr')),
                           (120, 'targetPlatform', 'u32')]),
    'hclSimClothData': (384, [
        (16, 'gravity', 'vec4'), (32, 'globalDampingPerSecond', 'f32'),
        (36, 'collisionTolerance', 'f32'),
        # Names guessed from Havok's SimulationInfo; vanilla sets 46 in 178 of 185 cloths,
        # 45 in 9, 44 in 2.
        (40, 'subSteps', 'u32'), (44, 'pinchDetectionEnabled', 'u8'),
        (45, 'landscapeCollisionEnabled', 'u8'), (46, 'transferMotionEnabled', 'u8'),
        (48, 'name', 'str'), (56, 'particleDatas', _s('ParticleData')),
        (72, 'fixedParticles', ('arr', 'u16')), (88, 'triangleIndices', ('arr', 'u16')),
        (104, 'triangleFlips', ('arr', 'u8')), (120, 'totalMass', 'f32'),
        (128, 'transformSetIndex', 'i32'), (136, 'transformIndices', ('arr', 'u32')),
        (152, 'offsets', ('arr', 'mat4')), (168, 'perInstanceCollidables', ('arr', 'ptr')),
        (184, 'staticConstraintSets', ('arr', 'ptr')),
        (200, 'antiPinchConstraintSets', ('arr', 'ptr')),
        (216, 'simClothPoses', ('arr', 'ptr')),
        (232, 'actions', ('arr', 'ptr')),
        (248, 'staticCollisionMasks', ('arr', 'u32')),
        (264, 'perParticlePinchDetectionEnabledFlags', ('arr', 'u8')),
        (280, 'collidablePinchingDatas', _s('PinchData')),
        (296, 'minPinchedParticleIndex', 'u16'), (298, 'maxPinchedParticleIndex', 'u16'),
        (300, 'maxCollisionPairs', 'u32'),
        (304, 'maxParticleRadius', 'f32'),
        (308, 'landscape', ('fixed', 'f32', 4)),
        # Set only in the 9 pieces with landscape collision (0.01 and a count: 20, 66, 153).
        (324, 'landscapeValue', 'f32'), (328, 'landscapeCount', 'u32'),
        (332, 'value332', 'u32'),                       # 1 in every vanilla piece
        # TransferMotionData, as Starfield's: how much of the character's motion the cloth
        # takes on, from which bone. All zeros lets every jump hit the cloth full force.
        (336, 'transferTransformSetIndex', 'u32'), (340, 'transferTransformIndex', 'u32'),
        (344, 'transferTranslationMotion', 'u8'), (348, 'minTranslationSpeed', 'f32'),
        (352, 'maxTranslationSpeed', 'f32'), (356, 'minTranslationBlend', 'f32'),
        (360, 'maxTranslationBlend', 'f32'), (364, 'transferRotationMotion', 'u8'),
        (368, 'minRotationSpeed', 'f32'), (372, 'maxRotationSpeed', 'f32'),
        (376, 'minRotationBlend', 'f32'), (380, 'maxRotationBlend', 'f32')]),
    'hclSimClothPose': (48, [(16, 'name', 'str'), (24, 'positions', ('arr', 'vec4'))]),
    'hclCollidable': (144, [(16, 'name', 'str'), (32, 'transform', 'mat4'),
                            (96, 'linearVelocity', 'vec4'), (112, 'angularVelocity', 'vec4'),
                            (128, 'usingVelocities', 'u8'),
                            (132, 'pinchDetectionRadius', 'f32'), (136, 'shape', 'ptr')]),
    'hclCapsuleShape': (96, [(32, 'start', 'vec4'), (48, 'end', 'vec4'), (64, 'dir', 'vec4'),
                             (80, 'radius', 'f32'), (84, 'capLenSqrdInv', 'f32')]),
    'hclTaperedCapsuleShape': (176, [
        (32, 'small', 'vec4'), (48, 'big', 'vec4'), (64, 'coneApex', 'vec4'),
        (80, 'coneAxis', 'vec4'), (96, 'lVec', 'vec4'), (112, 'dVec', 'vec4'),
        (128, 'tanThetaVecNeg', 'vec4'), (144, 'smallRadius', 'f32'), (148, 'bigRadius', 'f32'),
        (152, 'l', 'f32'), (156, 'd', 'f32'), (160, 'cosTheta', 'f32'), (164, 'sinTheta', 'f32'),
        (168, 'tanTheta', 'f32'), (172, 'tanThetaSqr', 'f32')]),
    'hclStandardLinkConstraintSet': (48, _CS + [(32, 'links', _s('Link'))]),
    'hclStretchLinkConstraintSet': (48, _CS + [(32, 'links', _s('Link'))]),
    'hclBendStiffnessConstraintSet': (64, _CS + [(32, 'links', _s('BendStiffnessLink')),
                                                 (48, 'useRestPoseConfig', 'u8')]),
    'hclBendLinkConstraintSet': (48, _CS + [(32, 'links', _s('BendLink'))]),
    'hclCompressibleLinkConstraintSet': (48, _CS + [(32, 'links', _s('CompressibleLink'))]),
    'hclLocalRangeConstraintSet': (64, _CS + [(32, 'localConstraints', _s('LocalConstraint')),
                                              (48, 'referenceMeshBufferIdx', 'u32'),
                                              (52, 'stiffness', 'f32'), (56, 'shapeType', 'u32'),
                                              (60, 'applyNormalComponent', 'u8')]),
    'hclBonePlanesConstraintSet': (64, _CS + [(32, 'bonePlanes', _s('BonePlane')),
                                              (48, 'transformSetIndex', 'u32')]),
    'hclVolumeConstraintMx': (96, _CS + [(32, 'frameBatchDatas', _s('FrameBatch')),
                                         (48, 'frameSingleDatas', _s('FrameSingle')),
                                         (64, 'applyBatchDatas', _s('ApplyBatch')),
                                         (80, 'applySingleDatas', _s('ApplySingle'))]),
    'hclBufferDefinition': (80, [(16, 'name', 'str'), (24, 'type', 'i32'),
                                 (28, 'subType', 'i32'), (32, 'numVertices', 'u32'),
                                 (36, 'numTriangles', 'u32'),
                                 (40, 'bufferLayout', ('struct', 'BufferLayout'))]),
    'hclScratchBufferDefinition': (96, [(16, 'name', 'str'), (24, 'type', 'i32'),
                                        (28, 'subType', 'i32'), (32, 'numVertices', 'u32'),
                                        (36, 'numTriangles', 'u32'),
                                        (40, 'bufferLayout', ('struct', 'BufferLayout')),
                                        (72, 'triangleIndices', ('arr', 'u16')),
                                        (88, 'storeNormals', 'u8'),
                                        (89, 'storeTangentsAndBiTangents', 'u8')]),
    'hclTransformSetDefinition': (32, [(16, 'name', 'str'), (24, 'type', 'i32'),
                                       (28, 'numTransforms', 'u32')]),
    'hclObjectSpaceSkinPNOperator': (192, _OP + [
        (32, 'boneFromSkinMeshTransforms', ('arr', 'mat4')),
        (48, 'transformSubset', ('arr', 'u16')),
        (64, 'outputBufferIndex', 'u32'), (68, 'transformSetIndex', 'u32'),
        (72, 'fourBlendEntries', _s('FourBlend')), (88, 'threeBlendEntries', _s('ThreeBlend')),
        (104, 'twoBlendEntries', _s('TwoBlend')), (120, 'oneBlendEntries', _s('OneBlend')),
        (136, 'controlBytes', ('arr', 'u8')),
        (152, 'startVertexIndex', 'u16'), (154, 'endVertexIndex', 'u16'),
        (156, 'partialWrite', 'u8'), (157, 'skinFlags', 'u8'), (160, 'localPNs', _s('LocalPN')),
        (176, 'localUnpackedPNs', ('arr', 'u8'))]),
    'hclMoveParticlesOperator': (64, _OP + [
        (32, 'vertexParticlePairs', _s('VertexParticlePair')),
        (48, 'simClothIndex', 'u32'), (52, 'refBufferIdx', 'u32')]),
    'hclSimulateOperator': (80, _OP + [
        (32, 'simClothIndex', 'u32'), (36, 'subSteps', 'u32'),
        (40, 'numberOfSolveIterations', 'i32'), (48, 'constraintExecution', ('arr', 'i32')),
        (64, 'adaptConstraintStiffness', 'u8')]),
    'hclSimpleMeshBoneDeformOperator': (80, _OP + [
        (32, 'inputBufferIdx', 'u32'), (36, 'outputTransformSetIdx', 'u32'),
        (40, 'triangleBonePairs', _s('TriangleBonePair')),
        (56, 'localBoneTransforms', ('arr', 'mat4')),
        (72, 'minTriangleArea', 'f32')]),
    'hclGatherAllVerticesOperator': (64, _OP + [
        (32, 'vertexInputFromVertexOutput', ('arr', 'i16')),
        (48, 'inputBufferIdx', 'u32'), (52, 'outputBufferIdx', 'u32'),
        (56, 'gatherNormals', 'u8'), (57, 'partialGather', 'u8')]),
    'hclGatherSomeVerticesOperator': (64, _OP + [
        (32, 'vertexPairs', _s('VertexPair')),
        (48, 'inputBufferIdx', 'u32'), (52, 'outputBufferIdx', 'u32'),
        (56, 'gatherNormals', 'u8')]),
    'hclCopyVerticesOperator': (64, _OP + [
        (32, 'inputBufferIdx', 'u32'), (36, 'outputBufferIdx', 'u32'),
        (40, 'numberOfVertices', 'u32'), (44, 'startVertexIn', 'u32'),
        (48, 'startVertexOut', 'u32'), (52, 'copyNormals', 'u8')]),
    'hclClothState': (96, [(16, 'name', 'str'), (24, 'operators', ('arr', 'u32')),
                           (40, 'usedBuffers', _s('BufferAccess')),
                           (56, 'usedTransformSets', _s('TransformSetAccess')),
                           (72, 'usedSimCloths', ('arr', 'u32'))]),
    'hkaSkeleton': (144, [(16, 'name', 'str'), (24, 'parentIndices', ('arr', 'i16')),
                          (40, 'bones', _s('Bone')), (56, 'referencePose', _s('QsTransform')),
                          (72, 'referenceFloats', ('arr', 'f32')),
                          (88, 'floatSlots', ('arr', 'str')),
                          (104, 'localFrames', ('arr', 'u8')),
                          (120, 'partitions', ('arr', 'u8'))]),
}
