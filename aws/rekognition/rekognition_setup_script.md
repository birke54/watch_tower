# Prerequisites:
- AWS account with programmatic access
  
# Configure AWS Resources
1. Create an S3 bucket for known faces
<pre> aws s3 mb s3://watch-tower-known-faces </pre>
2. Create an IAM role for Rekognition Video to publish to SNS (the role must have the AmazonRekognitionServiceRole policy attached)
3. Create an SNS topic for job-completion notifications (must begin with "AmazonRekognition" if using the service role.
<pre> aws sns create-topic --name AmazonRekognitionVideoAnalysisTopic </pre>pre>
4. Create an SQS queue and subscribe it to the SNS topic--this lets you poll for job updates.
<pre> aws sqs create-queue --queue-name RekognitionVideoResultsQueue </pre>

# Create and Populate a Face Collection
1. Create a collection to hold known faces
<pre> aws rekognition create-collection --collection-id KnownFaces </pre>
2. Index faces into that collection--upload clear, well-lit images of each person to S3 first, then:
<pre> aws rekognition index-faces \
--collection-id KnownFaces \
--image "S3_URL" \
--external-image-id "PERSON_ID" </pre>

# Testing the Face-Search job
1. Start an asynchronous face-search
<pre> aws rekognition start-face-search \
--collection-id KnownFaces \
--video "S3_URL" \
--notification-channel "SNS_TOPIC_ARN" \
--face-match-threshold 80 </pre>

*This will return a `JobId` immediately. Rekognition Video will publish a `Succeeded` or `Failed` message to the SNS topic when done.*

2. Poll SQS for the completion message
<pre> aws sqs receive-message \
--queue-url QUEUE_URL \
--wait-time-seconds 20 \
--max-number-of-messages 1`
3. Fetch face-search results
`aws rekognition get-face-search \
 --job-id JOB_ID </pre>
The response includes an array of Persons, each with:
- Person.FaceMatches: Details of matched faces (incl. ExternalImageId, FaceId, and confidence score)
- Timestamp: When in the video the person was recognized
- Person.Person: Bounding box and tracking ID for each detected eprson
