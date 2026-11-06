using System;
using System.Collections;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Threading.Tasks;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using Object = UnityEngine.Object;

namespace PsychologyVR.Editor
{
    public class PrototypeSessionNetworkTests
    {
        GameObject owner;
        PrototypeSession session;
        bool finished,originalBackground;
        const string ReplyJson="{\"generation\":8,\"relationship\":{\"status\":\"active\",\"trust\":82}}";
        static readonly BindingFlags Private=BindingFlags.Instance|BindingFlags.NonPublic;
        void Set(string name,object value)=>typeof(PrototypeSession).GetField(name,Private).SetValue(session,value);
        T Get<T>(string name)=>(T)typeof(PrototypeSession).GetField(name,Private).GetValue(session);
        void Relationship(RelationshipState value)=>typeof(PrototypeSession).GetProperty("Relationship").SetValue(session,value);
        void CancelLocal()=>typeof(PrototypeSession).GetMethod("CancelLocal",Private).Invoke(session,null);

        [UnitySetUp]
        public IEnumerator SetUp()
        {
            yield return new EnterPlayMode();
            originalBackground=Application.runInBackground;
            owner=new GameObject("Network race test");owner.SetActive(false);
            session=owner.AddComponent<PrototypeSession>();session.enabled=false;
            owner.SetActive(true); // Disabled behaviour can run coroutines, but never starts the game/service.
        }

        [UnityTearDown]
        public IEnumerator TearDown()
        {
            if(session)session.StopAllCoroutines();
            if(owner)Object.Destroy(owner);
            Application.runInBackground=originalBackground;
            yield return null;
            yield return new ExitPlayMode();
        }

        void InitializeRequest()
        {
            Set("version",7);Set("sessionId","old-session");Set("sessionGeneration",3);
            Set("streamTurnId","old-turn");Set("streamCompleted",2);Set("streamPartialSeconds",.25f);Set("busy",true);
            Relationship(new RelationshipState{status="active",trust=10});
        }
        void StartRequest(DelayedReply server,string method,bool reset=false)
        {
            session.serviceUrl=server.Url;finished=false;
            var args=method=="Invalidate"?new object[]{reset,Get<int>("version")}:new object[]{false};
            var routine=(IEnumerator)typeof(PrototypeSession).GetMethod(method,Private).Invoke(session,args);
            session.StartCoroutine(Complete(routine));
        }
        IEnumerator Complete(IEnumerator routine){yield return routine;finished=true;}
        IEnumerator Observe(Coroutine routine){yield return routine;finished=true;}
        static IEnumerator Until(Func<bool> condition)
        {
            float deadline=Time.realtimeSinceStartup+8;
            while(!condition()&&Time.realtimeSinceStartup<deadline)yield return null;
            Assert.That(condition(),Is.True,"Timed out waiting for loopback HTTP/coroutine completion.");
        }
        static void AssertRequest(DelayedReply server,string path)
        {
            Assert.That(server.Path,Is.EqualTo(path));
            var sent=JsonUtility.FromJson<RequestBody>(server.Request.Task.GetAwaiter().GetResult());
            Assert.That(sent.session_id,Is.EqualTo("old-session"));
            Assert.That(sent.turn_id,Is.EqualTo("old-turn"));
        }
        void AssertCurrentState(RelationshipState expected)
        {
            Assert.That(session.Relationship,Is.SameAs(expected),"A stale response replaced the current relationship.");
            Assert.That(Get<int>("sessionGeneration"),Is.EqualTo(31));
            Assert.That(Get<string>("streamTurnId"),Is.EqualTo("new-turn"));
            Assert.That(Get<int>("streamCompleted"),Is.EqualTo(4));
            Assert.That(Get<float>("streamPartialSeconds"),Is.EqualTo(.75f));
            Assert.That(Get<bool>("busy"),Is.True);
        }

        [UnityTest]
        public IEnumerator DelayedInterruptAndResetCannotOverwriteNewSession()
        {
            foreach(bool reset in new[]{false,true})using(var server=new DelayedReply())
            {
                InitializeRequest();StartRequest(server,"Invalidate",reset);
                yield return Until(()=>server.Request.Task.IsCompleted);AssertRequest(server,reset?"/reset":"/interrupt");
                // A reconnect has completed while the old response is still in flight.
                CancelLocal();Set("sessionId","new-session");Set("sessionGeneration",31);Set("busy",true);
                Set("streamTurnId","new-turn");Set("streamCompleted",4);Set("streamPartialSeconds",.75f);
                var current=new RelationshipState{status="active",trust=44};Relationship(current);
                server.Release(ReplyJson);yield return Until(()=>finished);
                Assert.That(server.Error,Is.Null);AssertCurrentState(current);
            }
        }

        [UnityTest]
        public IEnumerator DelayedFinishCannotOverwriteNewSessionOrNewTurn()
        {
            foreach(bool reconnect in new[]{true,false})using(var server=new DelayedReply())
            {
                InitializeRequest();StartRequest(server,"FinishStream");
                yield return Until(()=>server.Request.Task.IsCompleted);AssertRequest(server,"/turn/finish");
                // Reconnect or Stop cancels the old work before a new turn starts.
                CancelLocal();Set("busy",true);
                if(reconnect)Set("sessionId","new-session");
                Set("sessionGeneration",31);Set("streamTurnId","new-turn");
                Set("streamCompleted",4);Set("streamPartialSeconds",.75f);
                var current=new RelationshipState{status="active",trust=44};Relationship(current);
                server.Release(ReplyJson);yield return Until(()=>finished);
                Assert.That(server.Error,Is.Null);AssertCurrentState(current);
            }
        }

        [UnityTest]
        public IEnumerator CurrentInterruptAndResetStillComplete()
        {
            foreach(bool reset in new[]{false,true})using(var server=new DelayedReply())
            {
                InitializeRequest();StartRequest(server,"Invalidate",reset);
                yield return Until(()=>server.Request.Task.IsCompleted);AssertRequest(server,reset?"/reset":"/interrupt");
                server.Release(ReplyJson);yield return Until(()=>finished);
                Assert.That(server.Error,Is.Null);
                Assert.That(Get<int>("sessionGeneration"),Is.EqualTo(8));
                if(reset)Assert.That(session.Relationship,Is.Null);
                else Assert.That(session.Relationship.trust,Is.EqualTo(82));
                Assert.That(Get<string>("streamTurnId"),Is.Null);
                Assert.That(Get<int>("streamCompleted"),Is.Zero);Assert.That(Get<float>("streamPartialSeconds"),Is.Zero);
                Assert.That(Get<bool>("busy"),Is.False);
            }
        }

        [UnityTest]
        public IEnumerator CurrentFinishStillAppliesAndClearsPlayback()
        {
            using(var server=new DelayedReply())
            {
                InitializeRequest();StartRequest(server,"FinishStream");
                yield return Until(()=>server.Request.Task.IsCompleted);AssertRequest(server,"/turn/finish");
                server.Release(ReplyJson);yield return Until(()=>finished);
                Assert.That(server.Error,Is.Null);
                Assert.That(Get<int>("sessionGeneration"),Is.EqualTo(8));Assert.That(session.Relationship.trust,Is.EqualTo(82));
                Assert.That(Get<string>("streamTurnId"),Is.Null);
                Assert.That(Get<int>("streamCompleted"),Is.Zero);Assert.That(Get<float>("streamPartialSeconds"),Is.Zero);
            }
        }

        [UnityTest]
        public IEnumerator ServiceErrorsOnlyChangeTheCurrentRequestStatus()
        {
            foreach(bool stale in new[]{true,false})using(var server=new DelayedReply())
            {
                InitializeRequest();StartRequest(server,"Invalidate");
                yield return Until(()=>server.Request.Task.IsCompleted);AssertRequest(server,"/interrupt");
                if(stale){CancelLocal();Set("sessionId","new-session");}
                typeof(PrototypeSession).GetProperty("Status").SetValue(session,"New session ready.");
                server.Release("delayed HTTP failure",500);yield return Until(()=>finished);
                Assert.That(server.Error,Is.Null);
                Assert.That(session.Status,Is.EqualTo(stale?"New session ready.":"Service error: delayed HTTP failure"));
            }
        }

        [UnityTest]
        public IEnumerator CancellationBeforeNestedPostStartsCannotChangeStatus()
        {
            using(var server=new DelayedReply())
            {
                InitializeRequest();session.serviceUrl=server.Url;finished=false;
                var routine=(IEnumerator)typeof(PrototypeSession).GetMethod("Invalidate",Private).Invoke(session,new object[]{false,Get<int>("version")});
                int startedFrame=Time.frameCount;
                var pending=session.StartCoroutine(routine);
                // Cancel directly after native StartCoroutine returns, without a wrapper or test-frame yield.
                CancelLocal();int cancelledFrame=Time.frameCount;
                Set("sessionId","new-session");Set("sessionGeneration",31);
                var current=new RelationshipState{status="active",trust=44};Relationship(current);
                typeof(PrototypeSession).GetProperty("Status").SetValue(session,"New session ready.");
                session.StartCoroutine(Observe(pending));
                yield return Until(()=>server.Request.Task.IsCompleted);AssertRequest(server,"/interrupt");
                server.Release("immediately cancelled HTTP failure",500);yield return Until(()=>finished);
                string timing="StartCoroutine frame="+startedFrame+", CancelLocal frame="+cancelledFrame+", completed frame="+Time.frameCount;
                Assert.That(server.Error,Is.Null,timing);
                Assert.That(session.Status,Is.EqualTo("New session ready."),"An immediately cancelled nested POST changed the current status. "+timing);
                Assert.That(Get<int>("sessionGeneration"),Is.EqualTo(31),"An immediately cancelled request changed the current generation. "+timing);
                Assert.That(session.Relationship,Is.SameAs(current),"An immediately cancelled request replaced the current relationship. "+timing);
            }
        }

        // A real one-request HTTP endpoint. The test controls response ordering, not the client's transport.
        sealed class DelayedReply : IDisposable
        {
            readonly TcpListener listener=new TcpListener(IPAddress.Loopback,0);
            readonly TaskCompletionSource<string> response=new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
            public readonly TaskCompletionSource<string> Request=new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
            readonly Task worker;
            TcpClient client;
            int status=200;
            public string Url {get;}
            public string Path {get;private set;}
            public Exception Error {get;private set;}
            public DelayedReply()
            {
                listener.Start();Url="http://127.0.0.1:"+((IPEndPoint)listener.LocalEndpoint).Port;
                worker=Task.Run(Serve);
            }
            async Task Serve()
            {
                try
                {
                    using(client=await listener.AcceptTcpClientAsync())
                    using(var stream=client.GetStream())
                    using(var reader=new StreamReader(stream,Encoding.UTF8,false,1024,true))
                    {
                        string first=await reader.ReadLineAsync();Path=first.Split(' ')[1];
                        int length=0;string line;
                        while(!string.IsNullOrEmpty(line=await reader.ReadLineAsync()))
                            if(line.StartsWith("Content-Length:",StringComparison.OrdinalIgnoreCase))length=int.Parse(line.Substring(15).Trim());
                        var body=new char[length];int read=0;
                        while(read<length){int count=await reader.ReadAsync(body,read,length-read);if(count==0)throw new EndOfStreamException();read+=count;}
                        Request.TrySetResult(new string(body));
                        byte[] payload=Encoding.UTF8.GetBytes(await response.Task);
                        byte[] header=Encoding.ASCII.GetBytes("HTTP/1.1 "+status+(status==200?" OK":" Server Error")+"\r\nContent-Type: application/json\r\nContent-Length: "+payload.Length+"\r\nConnection: close\r\n\r\n");
                        await stream.WriteAsync(header,0,header.Length);await stream.WriteAsync(payload,0,payload.Length);await stream.FlushAsync();
                    }
                }
                catch(Exception error){Error=error;Request.TrySetException(error);}
            }
            public void Release(string json,int statusCode=200){status=statusCode;response.TrySetResult(json);}
            public void Dispose()
            {
                response.TrySetCanceled();listener.Stop();client?.Close();
                if(!worker.Wait(2000))throw new TimeoutException("Loopback HTTP worker did not stop.");
            }
        }
    }
}
