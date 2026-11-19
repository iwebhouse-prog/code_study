import { afterEach, describe, expect, it } from 'vitest'
import { ApiError } from '../../src/services/api-client'
import { projectService, toProject } from '../../src/services/project-service'
import { APP_PROJECT, RAW_PROJECT } from '../helpers/projects'
import { errorReply, mockApiClient, restoreApiClient } from '../helpers/http'

afterEach(() => {
  restoreApiClient()
})

describe('toProject', () => {
  it('maps snake_case fields to camelCase', () => {
    expect(toProject(RAW_PROJECT)).toEqual(APP_PROJECT)
  })

  it('keeps a null description', () => {
    expect(toProject({ ...RAW_PROJECT, description: null }).description).toBeNull()
  })
})

describe('projectService', () => {
  it('list: GET /projects and maps every project', async () => {
    const calls = mockApiClient(() => ({ status: 200, data: [RAW_PROJECT] }))
    expect(await projectService.list()).toEqual([APP_PROJECT])
    expect(calls).toEqual([{ method: 'get', url: '/projects', body: undefined }])
  })

  it('get: GET /projects/{id}', async () => {
    const calls = mockApiClient(() => ({ status: 200, data: RAW_PROJECT }))
    expect(await projectService.get('p-1')).toEqual(APP_PROJECT)
    expect(calls[0]).toMatchObject({ method: 'get', url: '/projects/p-1' })
  })

  it('create: POST /projects with title and description', async () => {
    const calls = mockApiClient(() => ({ status: 201, data: RAW_PROJECT }))
    const project = await projectService.create({ title: 'My Todo App', description: '설명' })
    expect(project).toEqual(APP_PROJECT)
    expect(calls[0]).toMatchObject({
      method: 'post',
      url: '/projects',
      body: { title: 'My Todo App', description: '설명' },
    })
  })

  it('create: leaves the description out when there is none', async () => {
    const calls = mockApiClient(() => ({ status: 201, data: RAW_PROJECT }))
    await projectService.create({ title: 'My Todo App' })
    expect(calls[0].body).toEqual({ title: 'My Todo App' })
  })

  it('update: PATCH sends only the given fields', async () => {
    const calls = mockApiClient(() => ({ status: 200, data: RAW_PROJECT }))
    await projectService.update('p-1', { title: '새 제목' })
    expect(calls[0]).toMatchObject({ method: 'patch', url: '/projects/p-1' })
    expect(calls[0].body).toEqual({ title: '새 제목' })
  })

  it('update: description null is sent to clear it', async () => {
    const calls = mockApiClient(() => ({ status: 200, data: RAW_PROJECT }))
    await projectService.update('p-1', { description: null })
    expect(calls[0].body).toEqual({ description: null })
  })

  it('remove: DELETE /projects/{id}', async () => {
    const calls = mockApiClient(() => ({ status: 204 }))
    await expect(projectService.remove('p-1')).resolves.toBeUndefined()
    expect(calls[0]).toMatchObject({ method: 'delete', url: '/projects/p-1' })
  })

  it('encodes the project id in the URL', async () => {
    const calls = mockApiClient(() => ({ status: 200, data: RAW_PROJECT }))
    await projectService.get('a/b')
    expect(calls[0].url).toBe('/projects/a%2Fb')
  })

  it('throws the API error with its message', async () => {
    mockApiClient(() => errorReply(403, 'forbidden', '이 프로젝트에 접근할 권한이 없습니다.'))
    const error = await projectService.get('p-1').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 403, message: '이 프로젝트에 접근할 권한이 없습니다.' })
  })
})
