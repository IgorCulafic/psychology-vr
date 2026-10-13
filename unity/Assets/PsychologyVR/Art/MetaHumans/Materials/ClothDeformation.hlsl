#ifndef PSYCHOLOGY_CLOTH_DEFORMATION_INCLUDED
#define PSYCHOLOGY_CLOTH_DEFORMATION_INCLUDED

// Short creases follow the bend of the actual thigh. No independent time/noise motion.
float3 KneeFold(float3 p,float4 knee,float3 axis)
{
    float3 d=p-knee.xyz;
    float along=dot(d,axis);
    float3 radial=d-axis*along;
    float radius=max(_ClothFoldRadius,.001);
    float envelope=exp(-dot(d,d)/(radius*radius));
    float wave=sin((along+.035)*115);
    return radial*rsqrt(max(dot(radial,radial),.0001))
        *wave*envelope*knee.w*_ClothFoldDepth;
}
float PalmPressure(float3 p,float4 palm)
{
    float3 d=p-palm.xyz;
    return exp(-dot(d,d)/(.055*.055))*palm.w*_ClothContactDepth;
}
float3 ClothOffset(float3 positionWS)
{
    return KneeFold(positionWS,_ClothKneeL,_ClothAxisL.xyz)
        +KneeFold(positionWS,_ClothKneeR,_ClothAxisR.xyz)
        -_ClothUp.xyz*(PalmPressure(positionWS,_ClothHandL)+PalmPressure(positionWS,_ClothHandR));
}
void DeformCloth(inout float4 positionOS,inout float3 normalOS,inout float4 tangentOS)
{
    float3 position=TransformObjectToWorld(positionOS.xyz);
    float3 normal=TransformObjectToWorldNormal(normalOS);
    float3 tangent=TransformObjectToWorldDir(tangentOS.xyz);
    float3 bitangent=cross(normal,tangent);
    float3 offset=ClothOffset(position);
    float3 t=tangent+(ClothOffset(position+tangent*.001)-offset)/.001;
    float3 b=bitangent+(ClothOffset(position+bitangent*.001)-offset)/.001;
    positionOS.xyz=TransformWorldToObject(position+offset);
    normalOS=TransformWorldToObjectNormal(normalize(cross(t,b)));
    tangentOS.xyz=TransformWorldToObjectDir(normalize(t));
}
void DeformClothShadow(inout float4 positionOS,inout float3 normalOS)
{
    float3 normal=normalize(normalOS);
    float3 axis=abs(normal.y)<.9?float3(0,1,0):float3(1,0,0);
    float4 tangent=float4(normalize(cross(axis,normal)),1);
    DeformCloth(positionOS,normalOS,tangent);
}
#endif
