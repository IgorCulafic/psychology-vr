#ifndef PSYCHOLOGY_CUSHION_DEFORMATION_INCLUDED
#define PSYCHOLOGY_CUSHION_DEFORMATION_INCLUDED

// xy: pressure centre in chair space; z: indentation in metres.

float CushionPressure(float2 position,float4 pressure,float2 radius,float2 direction)
{
    float2 delta=position-pressure.xy;
    float2 distance=float2(dot(delta,float2(direction.y,-direction.x)),dot(delta,direction))/radius;
    return exp(-2*dot(distance,distance))*pressure.z;
}

float3 CushionOffset(float3 positionWS)
{
    float3 relative=positionWS-_CushionOrigin.xyz;
    float3 p=float3(dot(relative,_CushionRight.xyz),dot(relative,_CushionUp.xyz),dot(relative,_CushionForward.xyz));
    float2 seatRadius=float2(_CushionSeatRadiusX,_CushionSeatRadiusZ);
    float2 thighRadius=float2(_CushionThighRadiusX,_CushionThighRadiusZ);
    float leftSeat=CushionPressure(p.xz,_CushionSeat,seatRadius,float2(0,1));
    float rightSeat=CushionPressure(p.xz,_CushionRightSeat,seatRadius,float2(0,1));
    float leftThigh=CushionPressure(p.xz,_CushionLeftThigh,thighRadius,_CushionThighDirections.xy);
    float rightThigh=CushionPressure(p.xz,_CushionRightThigh,thighRadius,_CushionThighDirections.zw);
    // A smooth union joins the contacts without adding four full-depth dents together.
    float maximumDepth=max(_CushionSeatDepth,_CushionThighDepth);
    float seat=0;
    if(maximumDepth>0)
        seat=maximumDepth*(1-(1-leftSeat/maximumDepth)*(1-rightSeat/maximumDepth)
            *(1-leftThigh/maximumDepth)*(1-rightThigh/maximumDepth));
    seat*=smoothstep(.38,.52,p.y)*(1-smoothstep(.57,.63,p.y));
    float2 backDistance=(p.xy-_CushionBack.xy)/float2(_CushionBackRadiusX,_CushionBackRadiusY);
    float back=exp(-2*dot(backDistance,backDistance));
    back*=smoothstep(.59,.68,p.y)*(1-smoothstep(.97,1.04,p.y));
    return -_CushionUp.xyz*seat
        -(_CushionForward.xyz*.9165+_CushionUp.xyz*.4)*back*_CushionBack.z;
}

void DeformCushion(inout float4 positionOS,inout float3 normalOS,inout float4 tangentOS)
{
    float3 position=TransformObjectToWorld(positionOS.xyz);
    float3 normal=TransformObjectToWorldNormal(normalOS);
    float3 tangent=TransformObjectToWorldDir(tangentOS.xyz);
    float3 bitangent=cross(normal,tangent);
    float3 offset=CushionOffset(position);
    // Differentiate the same displacement for the normal and fabric tangent.
    float3 t=tangent+(CushionOffset(position+tangent*.001)-offset)/.001;
    float3 b=bitangent+(CushionOffset(position+bitangent*.001)-offset)/.001;
    positionOS.xyz=TransformWorldToObject(position+offset);
    normalOS=TransformWorldToObjectNormal(normalize(cross(t,b)));
    tangentOS.xyz=TransformWorldToObjectDir(normalize(t));
}

void DeformCushionShadow(inout float4 positionOS,inout float3 normalOS)
{
    float3 normal=normalize(normalOS);
    float3 axis=abs(normal.y)<.9?float3(0,1,0):float3(1,0,0);
    float4 tangent=float4(normalize(cross(axis,normal)),1);
    DeformCushion(positionOS,normalOS,tangent);
}
#endif
